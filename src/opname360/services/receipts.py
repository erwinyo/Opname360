"""The till: pricing a cart and completing Receipts, returns and exchanges."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlmodel import Session, col, func, select

from opname360.core.config import settings
from opname360.core.errors import ConflictError, ForbiddenError, NotFoundError
from opname360.core.formatting import rupiah, sku_label
from opname360.models import (
    Cart,
    MovementReason,
    Payment,
    PaymentMethod,
    PaymentPublic,
    Promotion,
    Quote,
    QuotedLine,
    QuotedReturn,
    Receipt,
    ReceiptCreate,
    ReceiptFilter,
    ReceiptKind,
    ReceiptLine,
    ReceiptLinePublic,
    ReceiptPage,
    ReceiptPublic,
    ReceiptStatus,
    ReceiptSummary,
    ReturnCondition,
    Role,
    Shift,
    Sku,
    TillSku,
    User,
)
from opname360.models._types import utc_now
from opname360.services import (
    activity_log,
    catalogue,
    costing,
    documents,
    payment_methods,
    posting,
    promotions,
    shop_settings,
)
from opname360.services import shifts as shifts_service


DOCUMENT_TYPE = 'receipt'
PREFIXES = {
    ReceiptKind.sale: 'PJ',  # Penjualan
    ReceiptKind.return_: 'RJ',  # Retur Jual
    ReceiptKind.exchange: 'TT',  # Tukar Tambah
}
KIND_WORDS = {
    ReceiptKind.sale: 'penjualan',
    ReceiptKind.return_: 'retur penjualan',
    ReceiptKind.exchange: 'tukar tambah',
}
SKUS_SHOWN = 20


def whole_rupiah(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def find_skus(session: Session, search: str) -> list[TillSku]:
    """A scan finds its one SKU; typed text finds SKUs by name (rule 5)."""
    return [
        TillSku.model_validate(option)
        for option in catalogue.search_skus(session, search, limit=SKUS_SHOWN)
    ]


@dataclass
class _Priced:
    sku: Sku
    quantity: Decimal
    unit_price: int
    promotion: Promotion | None
    discount: int

    @property
    def gross(self) -> int:
        return whole_rupiah(self.unit_price * self.quantity)

    @property
    def line_total(self) -> int:
        return self.gross - self.discount


def _price(session: Session, cart: Cart) -> list[_Priced]:
    """Each SKU once, at its Selling Price now, less the biggest running
    Promotion (rules 6 and 7)."""
    quantities: dict[int, Decimal] = {}
    for line in cart.lines:
        quantities[line.sku_id] = (
            quantities.get(line.sku_id, Decimal(0)) + line.quantity
        )
    skus = {
        sku.id: sku
        for sku in session.exec(
            select(Sku).where(col(Sku.id).in_(quantities))
        ).all()
    }
    for sku_id in quantities:
        sku = skus.get(sku_id)
        if sku is None:
            raise NotFoundError('Barang di keranjang tidak ditemukan.')
        if not sku.is_active:
            label = sku_label(sku.product.name, sku.size, sku.color)
            raise ConflictError(f'{label} sudah tidak dijual.')
    discounts = promotions.best_discounts(
        session, list(skus.values()), utc_now()
    )
    priced = []
    for sku_id, quantity in quantities.items():
        sku = skus[sku_id]
        promotion, unit_discount = discounts.get(sku_id, (None, Decimal(0)))
        priced.append(
            _Priced(
                sku=sku,
                quantity=quantity,
                unit_price=sku.selling_price,
                promotion=promotion,
                discount=whole_rupiah(unit_discount * quantity),
            )
        )
    return priced


@dataclass
class _Returned:
    original: ReceiptLine
    sku: Sku
    # Units coming back.
    quantity: Decimal
    condition: ReturnCondition
    refund: int

    @property
    def gross(self) -> int:
        return whole_rupiah(self.original.unit_price * self.quantity)


def _shop_day(moment: datetime) -> date:
    return moment.astimezone(ZoneInfo(settings.timezone)).date()


def receipt_for_return(session: Session, number: str) -> Receipt:
    """The Receipt a customer brings back, if it can still be returned."""
    number = number.strip().upper()
    receipt = session.exec(
        select(Receipt).where(Receipt.number == number)
    ).first()
    if receipt is None:
        raise NotFoundError(f'Struk {number} tidak ditemukan.')
    _check_returnable(session, receipt)
    return receipt


def _check_returnable(session: Session, receipt: Receipt) -> None:
    """Rules 12, 13 and 19: not voided, and inside today's Return Window."""
    if receipt.status == ReceiptStatus.voided:
        raise ConflictError(
            f'Struk {receipt.number} sudah dibatalkan, jadi tidak bisa '
            'diretur.'
        )
    if not any(line.quantity > 0 for line in receipt.lines):
        raise ConflictError(
            f'Struk {receipt.number} tidak berisi barang yang dibeli.'
        )
    window = shop_settings.get_settings(session).return_window_days
    sold_on = _shop_day(receipt.created_at)
    if (documents.shop_now().date() - sold_on).days > window:
        raise ConflictError(
            f'Struk {receipt.number} dari {sold_on:%d-%m-%Y} sudah lewat '
            f'batas retur {window} hari.'
        )


def _returned_so_far(
    session: Session, original_receipt_id: int
) -> dict[int, tuple[Decimal, int]]:
    """Per line of a Receipt: units back so far and what they refunded.
    A voided return gave nothing back."""
    rows = session.exec(
        select(
            ReceiptLine.original_line_id,
            func.sum(-col(ReceiptLine.quantity)),
            func.sum(-col(ReceiptLine.line_total)),
        )
        .join(Receipt, col(ReceiptLine.receipt_id) == Receipt.id)
        .where(
            Receipt.original_receipt_id == original_receipt_id,
            Receipt.status == ReceiptStatus.completed,
            col(ReceiptLine.original_line_id).is_not(None),
        )
        .group_by(col(ReceiptLine.original_line_id))
    ).all()
    return {
        line_id: (quantity, int(refunded))
        for line_id, quantity, refunded in rows
        if line_id is not None
    }


def _price_returns(session: Session, cart: Cart) -> list[_Returned]:
    """What comes back, each refunded at what was paid for it after
    discount (rules 12 and 14)."""
    if not cart.returns:
        return []
    if cart.original_receipt_id is None:
        raise ConflictError('Retur harus dari struk asalnya.')
    original = get_receipt(session, cart.original_receipt_id)
    _check_returnable(session, original)
    sold = {line.id: line for line in original.lines if line.quantity > 0}
    so_far = _returned_so_far(session, cart.original_receipt_id)
    returned: list[_Returned] = []
    for row in cart.returns:
        line = sold.get(row.original_line_id)
        if line is None:
            raise NotFoundError(
                f'Barang itu tidak ada di struk {original.number}.'
            )
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        back, refunded = so_far.get(row.original_line_id, (Decimal(0), 0))
        left = line.quantity - back
        if row.quantity > left:
            label = sku_label(sku.product.name, sku.size, sku.color)
            raise ConflictError(
                f'{label}: paling banyak {left.normalize():f} '
                f'{sku.stock_unit} yang masih bisa diretur dari '
                f'{original.number}.'
            )
        # Refunds add up to exactly the line total once all units are back.
        back += row.quantity
        refund = (
            whole_rupiah(line.line_total * back / line.quantity) - refunded
        )
        so_far[row.original_line_id] = (back, refunded + refund)
        returned.append(
            _Returned(
                original=line,
                sku=sku,
                quantity=row.quantity,
                condition=row.condition,
                refund=refund,
            )
        )
    return returned


@dataclass
class _Totals:
    subtotal: int
    discount_total: int
    refund_total: int

    @property
    def total(self) -> int:
        return self.subtotal - self.discount_total - self.refund_total


def _totals(priced: list[_Priced], returned: list[_Returned]) -> _Totals:
    return _Totals(
        subtotal=sum(line.gross for line in priced),
        discount_total=sum(line.discount for line in priced),
        refund_total=sum(item.refund for item in returned),
    )


def quote(session: Session, cart: Cart) -> Quote:
    priced = _price(session, cart)
    returned = _price_returns(session, cart)
    totals = _totals(priced, returned)
    return Quote(
        lines=[_quoted(line) for line in priced],
        returns=[
            QuotedReturn(
                original_line_id=item.original.id or 0,
                sku_id=item.sku.id or 0,
                quantity=item.quantity,
                condition=item.condition,
                refund=item.refund,
            )
            for item in returned
        ],
        subtotal=totals.subtotal,
        discount_total=totals.discount_total,
        refund_total=totals.refund_total,
        total=totals.total,
    )


def _quoted(line: _Priced) -> QuotedLine:
    sku = line.sku
    return QuotedLine(
        sku_id=line.sku.id or 0,
        product_name=sku.product.name,
        size=sku.size,
        color=sku.color,
        code=sku.code,
        stock_unit=sku.stock_unit,
        quantity=line.quantity,
        unit_price=line.unit_price,
        promotion_name=line.promotion.name if line.promotion else None,
        discount=line.discount,
        line_total=line.line_total,
    )


def complete(
    session: Session, receipt_in: ReceiptCreate, *, actor: User
) -> Receipt:
    """A sale, return or exchange: price it again, settle the money, move
    the stock (rules 6, 8, 9 and 12-16)."""
    shift = shifts_service.selling_shift(session, actor)
    assert shift.id is not None
    if receipt_in.original_receipt_id is not None:
        # Two returns at once can't both take back the last unit.
        get_receipt(session, receipt_in.original_receipt_id)
        documents.lock(session, Receipt, receipt_in.original_receipt_id)
    priced = _price(session, receipt_in)
    returned = _price_returns(session, receipt_in)
    if not priced and not returned:
        raise ConflictError('Keranjang masih kosong.')
    totals = _totals(priced, returned)
    if totals.total != receipt_in.expected_total:
        raise ConflictError(
            f'Harga berubah: totalnya sekarang {rupiah(totals.total)}. '
            'Periksa lagi sebelum menerima pembayaran.'
        )
    if not returned:
        kind = ReceiptKind.sale
    else:
        kind = ReceiptKind.exchange if priced else ReceiptKind.return_
    payments, change = _settle(session, totals.total, receipt_in, kind)

    assert actor.id is not None
    receipt = Receipt(
        number=documents.next_number(session, PREFIXES[kind]),
        kind=kind,
        shift_id=shift.id,
        location_id=shift.location_id,
        cashier_id=actor.id,
        original_receipt_id=(
            receipt_in.original_receipt_id if returned else None
        ),
        subtotal=totals.subtotal,
        discount_total=totals.discount_total,
        refund_total=totals.refund_total,
        total=totals.total,
        change_given=change,
    )
    session.add(receipt)
    session.flush()
    assert receipt.id is not None

    source = costing.Source(DOCUMENT_TYPE, receipt.id, receipt.number)
    # SKU order, like every stock document, avoids deadlocks; what comes
    # back goes in before the same SKU goes out.
    items: list[_Priced | _Returned] = [*returned, *priced]
    for item in sorted(
        items,
        key=lambda item: (item.sku.id or 0, isinstance(item, _Priced)),
    ):
        if isinstance(item, _Returned):
            _take_back(
                session, receipt, item, shift.location_id, source, actor
            )
        else:
            _sell(session, receipt, item, shift.location_id, source, actor)
    for method_id, amount, reference in payments:
        session.add(
            Payment(
                receipt_id=receipt.id,
                payment_method_id=method_id,
                amount=amount,
                reference=reference,
            )
        )
    activity_log.record(
        session,
        actor=actor,
        action='receipt.complete',
        summary=_summary(session, receipt),
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    posting.receipt(session, receipt, actor=actor)
    session.commit()
    session.refresh(receipt)
    return receipt


def _sell(
    session: Session,
    receipt: Receipt,
    line: _Priced,
    location_id: int,
    source: costing.Source,
    actor: User,
) -> None:
    """Stock out at its cost; Negative Stock never stops a sale (rule 9)."""
    assert receipt.id is not None
    assert line.sku.id is not None
    movement = costing.issue(
        session,
        sku=line.sku,
        location_id=location_id,
        quantity=line.quantity,
        reason=MovementReason.sale,
        source=source,
        actor=actor,
    )
    session.add(
        ReceiptLine(
            receipt_id=receipt.id,
            sku_id=line.sku.id,
            quantity=line.quantity,
            unit_price=line.unit_price,
            promotion_id=line.promotion.id if line.promotion else None,
            discount=line.discount,
            line_total=line.line_total,
            unit_cogs=costing.money(-movement.value / line.quantity),
        )
    )


def _take_back(
    session: Session,
    receipt: Receipt,
    item: _Returned,
    location_id: int,
    source: costing.Source,
    actor: User,
) -> None:
    """Back into stock at the cost it was sold at; a Damaged Return leaves
    again at once, so the Stock Card shows both (rule 15)."""
    assert receipt.id is not None
    assert item.sku.id is not None
    original = item.original
    movement = costing.receive(
        session,
        sku=item.sku,
        location_id=location_id,
        quantity=item.quantity,
        value=costing.money(item.quantity * original.unit_cogs),
        reason=MovementReason.customer_return,
        source=source,
        actor=actor,
        sets_latest_cost=False,
    )
    if item.condition == ReturnCondition.damaged:
        session.flush()
        costing.issue(
            session,
            sku=item.sku,
            location_id=location_id,
            quantity=item.quantity,
            reason=MovementReason.write_off,
            source=source,
            actor=actor,
            unit_cost=original.unit_cogs,
            layer_of=movement.id,
        )
    gross = -item.gross
    session.add(
        ReceiptLine(
            receipt_id=receipt.id,
            sku_id=item.sku.id,
            quantity=-item.quantity,
            unit_price=original.unit_price,
            promotion_id=original.promotion_id,
            discount=gross + item.refund,
            line_total=-item.refund,
            unit_cogs=original.unit_cogs,
            original_line_id=original.id,
            condition=item.condition,
        )
    )


def _summary(session: Session, receipt: Receipt) -> str:
    words = f'{KIND_WORDS[receipt.kind].capitalize()} {receipt.number}'
    if receipt.original_receipt_id:
        original = session.get(Receipt, receipt.original_receipt_id)
        assert original is not None
        words += f' dari {original.number}'
    if receipt.total > 0:
        return f'{words}: {rupiah(receipt.total)}.'
    if receipt.total < 0:
        return f'{words}: dikembalikan {rupiah(-receipt.total)}.'
    return f'{words}: tanpa selisih.'


def _refund(
    session: Session, total: int, receipt_in: ReceiptCreate, kind: ReceiptKind
) -> tuple[int, int, str | None]:
    """Money back: cash unless the Cashier picks another method for a
    return; an exchange always pays back in cash (rules 14 and 16)."""
    if receipt_in.refund_method_id is None:
        method = payment_methods.cash_method(session)
    else:
        method = payment_methods.get_method(
            session, receipt_in.refund_method_id
        )
        if not method.is_active:
            raise ConflictError(f'Metode {method.name} sedang nonaktif.')
        if kind == ReceiptKind.exchange and not method.is_cash:
            raise ConflictError('Selisih tukar tambah dikembalikan tunai.')
    assert method.id is not None
    return method.id, total, None


def _settle(
    session: Session, total: int, receipt_in: ReceiptCreate, kind: ReceiptKind
) -> tuple[list[tuple[int, int, str | None]], int]:
    """The payments to keep as (method, amount, reference), and the
    change (rules 8, 14 and 16)."""
    payments_in = receipt_in.payments
    if total <= 0 and payments_in:
        raise ConflictError('Tidak ada yang perlu dibayar pelanggan.')
    if total == 0:
        return [], 0
    if total < 0:
        return [_refund(session, total, receipt_in, kind)], 0
    methods = {
        method.id: method
        for method in session.exec(
            select(PaymentMethod).where(
                col(PaymentMethod.id).in_(
                    [p.payment_method_id for p in payments_in]
                )
            )
        ).all()
    }
    cash = non_cash = 0
    for payment in payments_in:
        method = methods.get(payment.payment_method_id)
        if method is None or not method.is_active:
            raise ConflictError('Metode pembayaran itu tidak tersedia.')
        if method.is_cash:
            cash += payment.amount
        elif not payment.confirmed:
            raise ConflictError(
                f'Pastikan pembayaran {method.name} sudah masuk, lalu '
                'centang konfirmasinya.'
            )
        else:
            non_cash += payment.amount
    if non_cash > total:
        raise ConflictError(
            'Pembayaran non-tunai melebihi total. Kembalian hanya dari '
            'uang tunai.'
        )
    if cash + non_cash < total:
        raise ConflictError(
            f'Pembayaran kurang {rupiah(total - cash - non_cash)}.'
        )
    change = cash + non_cash - total
    kept = []
    left = change
    for payment in payments_in:
        amount = payment.amount
        if methods[payment.payment_method_id].is_cash and left:
            taken = min(amount, left)
            amount -= taken
            left -= taken
        if amount:
            reference = (payment.reference or '').strip() or None
            kept.append((payment.payment_method_id, amount, reference))
    return kept, change


def get_receipt(session: Session, receipt_id: int) -> Receipt:
    receipt = session.get(Receipt, receipt_id)
    if receipt is None:
        raise NotFoundError('Struk tidak ditemukan.')
    return receipt


def list_receipts(session: Session, filters: ReceiptFilter) -> ReceiptPage:
    """A Shift's Receipts, the latest first."""
    query = select(Receipt).where(Receipt.shift_id == filters.shift_id)
    total = session.exec(
        select(func.count()).select_from(query.subquery())
    ).one()
    receipts = session.exec(
        query.order_by(col(Receipt.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    ids = [receipt.id for receipt in receipts]
    methods: dict[int, list[str]] = {}
    for receipt_id, name in session.exec(
        select(Payment.receipt_id, PaymentMethod.name)
        .join(
            PaymentMethod, col(Payment.payment_method_id) == PaymentMethod.id
        )
        .where(col(Payment.receipt_id).in_(ids))
        .order_by(col(Payment.id))
    ).all():
        methods.setdefault(receipt_id, []).append(name)
    line_counts = dict(
        session.exec(
            select(ReceiptLine.receipt_id, func.count())
            .where(col(ReceiptLine.receipt_id).in_(ids))
            .group_by(col(ReceiptLine.receipt_id))
        ).all()
    )
    return ReceiptPage(
        items=[
            ReceiptSummary.model_validate(
                receipt,
                update={
                    'cashier_name': documents.user_name(
                        session, receipt.cashier_id
                    )
                    or '',
                    'methods': ', '.join(
                        dict.fromkeys(methods.get(receipt.id or 0, []))
                    ),
                    'line_count': line_counts.get(receipt.id, 0),
                },
            )
            for receipt in receipts
        ],
        total=total,
    )


def void(
    session: Session, receipt: Receipt, reason: str, *, actor: User
) -> Receipt:
    """Cancel a Receipt inside its own open Shift: the stock moves back and
    its money no longer counts (rule 11)."""
    assert receipt.id is not None
    # The Shift first, like a sale: it can't close halfway through.
    shift = session.get(
        Shift,
        receipt.shift_id,
        with_for_update={'read': True},
        populate_existing=True,
    )
    assert shift is not None
    receipt = documents.lock(session, Receipt, receipt.id)
    assert receipt.id is not None
    if receipt.status == ReceiptStatus.voided:
        raise ConflictError(f'Struk {receipt.number} sudah dibatalkan.')
    if shift.closed_at is not None:
        raise ConflictError(
            f'Shift {shift.number} sudah ditutup. Sekarang penjualan ini '
            'hanya bisa dibatalkan lewat retur.'
        )
    if receipt.cashier_id != actor.id and actor.role != Role.owner:
        raise ForbiddenError(
            'Struk hanya bisa dibatalkan oleh kasir yang membuatnya atau '
            'Pemilik.'
        )
    returned = session.exec(
        select(Receipt.number).where(
            Receipt.original_receipt_id == receipt.id,
            Receipt.status == ReceiptStatus.completed,
        )
    ).first()
    if returned is not None:
        raise ConflictError(
            f'Sudah ada {returned} dari struk {receipt.number}; batalkan '
            'struk itu dulu.'
        )
    documents.write_reversal(
        session,
        document_type=DOCUMENT_TYPE,
        document_id=receipt.id,
        label=f'struk {receipt.number}',
        reason=reason,
        actor=actor,
    )
    receipt.status = ReceiptStatus.voided
    receipt.void_reason = reason.strip()
    receipt.voided_by = actor.id
    receipt.voided_at = utc_now()
    session.add(receipt)
    session.commit()
    return receipt


def print_receipt(
    session: Session, receipt: Receipt, *, actor: User
) -> Receipt:
    """Count the printout: every one after the first is a copy (rule 10)."""
    assert receipt.id is not None
    receipt = documents.lock(session, Receipt, receipt.id)
    receipt.print_count += 1
    session.add(receipt)
    if receipt.print_count > 1:
        activity_log.record(
            session,
            actor=actor,
            action='receipt.reprint',
            summary=f'Mencetak ulang struk {receipt.number}.',
            entity_type=DOCUMENT_TYPE,
            entity_id=receipt.id,
        )
    session.commit()
    return receipt


def receipt_public(session: Session, receipt: Receipt) -> ReceiptPublic:
    shift = session.get(Shift, receipt.shift_id)
    assert shift is not None
    original = (
        session.get(Receipt, receipt.original_receipt_id)
        if receipt.original_receipt_id
        else None
    )
    assert receipt.id is not None
    returned = _returned_so_far(session, receipt.id)
    lines = []
    for line in receipt.lines:
        sku = session.get(Sku, line.sku_id)
        assert sku is not None
        lines.append(
            ReceiptLinePublic.model_validate(
                line,
                update={
                    'product_name': sku.product.name,
                    'size': sku.size,
                    'color': sku.color,
                    'code': sku.code,
                    'stock_unit': sku.stock_unit,
                    'promotion_name': _promotion_name(
                        session, line.promotion_id
                    ),
                    'returned_quantity': returned.get(
                        line.id or 0, (Decimal(0), 0)
                    )[0],
                },
            )
        )
    payments = []
    for payment in receipt.payments:
        method = session.get(PaymentMethod, payment.payment_method_id)
        assert method is not None
        payments.append(
            PaymentPublic.model_validate(
                payment,
                update={'method_name': method.name, 'is_cash': method.is_cash},
            )
        )
    return ReceiptPublic.model_validate(
        receipt,
        update={
            'shift_number': shift.number,
            'cashier_name': documents.user_name(session, receipt.cashier_id)
            or '',
            'original_receipt_number': original.number if original else None,
            'voided_by_name': documents.user_name(session, receipt.voided_by),
            'lines': lines,
            'payments': payments,
        },
    )


def _promotion_name(session: Session, promotion_id: int | None) -> str | None:
    promotion = session.get(Promotion, promotion_id) if promotion_id else None
    return promotion.name if promotion else None
