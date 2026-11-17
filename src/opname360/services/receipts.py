"""The till: pricing a cart and completing Receipts."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlmodel import Session, col, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.core.formatting import rupiah, sku_label
from opname360.models import (
    Cart,
    MovementReason,
    Payment,
    PaymentIn,
    PaymentMethod,
    PaymentPublic,
    Promotion,
    Quote,
    QuotedLine,
    Receipt,
    ReceiptCreate,
    ReceiptKind,
    ReceiptLine,
    ReceiptLinePublic,
    ReceiptPublic,
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
    promotions,
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


def quote(session: Session, cart: Cart) -> Quote:
    priced = _price(session, cart)
    return Quote(
        lines=[_quoted(line) for line in priced],
        subtotal=sum(line.gross for line in priced),
        discount_total=sum(line.discount for line in priced),
        refund_total=0,
        total=sum(line.line_total for line in priced),
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
    """Price the cart again, take the payment, write the stock out
    (rules 6, 8 and 9)."""
    shift = shifts_service.selling_shift(session, actor)
    assert shift.id is not None
    priced = _price(session, receipt_in)
    if not priced:
        raise ConflictError('Keranjang masih kosong.')
    total = sum(line.line_total for line in priced)
    if total != receipt_in.expected_total:
        raise ConflictError(
            f'Harga berubah: totalnya sekarang {rupiah(total)}. '
            'Periksa lagi sebelum menerima pembayaran.'
        )
    payments, change = _settle(session, total, receipt_in.payments)

    kind = ReceiptKind.sale
    assert actor.id is not None
    receipt = Receipt(
        number=documents.next_number(session, PREFIXES[kind]),
        kind=kind,
        shift_id=shift.id,
        location_id=shift.location_id,
        cashier_id=actor.id,
        subtotal=sum(line.gross for line in priced),
        discount_total=sum(line.discount for line in priced),
        total=total,
        change_given=change,
    )
    session.add(receipt)
    session.flush()
    assert receipt.id is not None

    source = costing.Source(DOCUMENT_TYPE, receipt.id, receipt.number)
    # SKU order, like every stock document, avoids deadlocks.
    for line in sorted(priced, key=lambda line: line.sku.id or 0):
        assert line.sku.id is not None
        movement = costing.issue(
            session,
            sku=line.sku,
            location_id=shift.location_id,
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
        summary=(
            f'{KIND_WORDS[kind].capitalize()} {receipt.number}: '
            f'{rupiah(total)}.'
        ),
        entity_type=DOCUMENT_TYPE,
        entity_id=receipt.id,
    )
    session.commit()
    session.refresh(receipt)
    return receipt


def _settle(
    session: Session, total: int, payments_in: list[PaymentIn]
) -> tuple[list[tuple[int, int, str | None]], int]:
    """The payments to keep as (method, amount, reference), and the
    change (rule 8)."""
    if total == 0:
        if payments_in:
            raise ConflictError('Tidak ada yang perlu dibayar.')
        return [], 0
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
