"""What each document posts to the Ledger (slice 5's postings table).

Each function runs inside the caller's transaction, so a document and its
journal entry are saved together or not at all (rule 3). Every Stock
Movement's value goes to Persediaan exactly, so Persediaan always equals
the Stock Value in the Stok screen (rule 6); a movement of value without
goods (costing rule 6) is COGS.
"""

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError
from opname360.models import (
    AccountRole,
    DocumentStatus,
    EntrySource,
    GoodsReceipt,
    JournalEntry,
    MovementReason,
    OpnameLine,
    OpnameStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    ProductionReceipt,
    Receipt,
    ReceiptKind,
    ReceiptLine,
    Resolution,
    Reversal,
    Shift,
    ShopSettings,
    StockMovement,
    StockOpname,
    Supplier,
    SupplierReturn,
    User,
)
from opname360.services import ledger
from opname360.services.costing import Source
from opname360.services.ledger import Amount


ZERO = Decimal(0)


def _movements(
    session: Session, document_type: str, document_id: int
) -> list[StockMovement]:
    """The movements a document made itself, not its Reversal's."""
    return list(
        session.exec(
            select(StockMovement)
            .where(
                StockMovement.document_type == document_type,
                StockMovement.document_id == document_id,
                StockMovement.reason != MovementReason.reversal,
            )
            .order_by(col(StockMovement.id))
        ).all()
    )


def _stock(session: Session, movements: list[StockMovement]) -> list[Amount]:
    """Persediaan by every movement's value. A cost adjustment (value
    without goods) goes against Harga Pokok Penjualan."""
    inventory = ledger.account_of(session, AccountRole.inventory)
    cogs = ledger.account_of(session, AccountRole.cogs)
    amounts = []
    for movement in movements:
        amounts.append(Amount(inventory, movement.value))
        if movement.quantity == 0:
            amounts.append(Amount(cogs, -movement.value))
    return amounts


def _post(
    session: Session,
    *,
    at: datetime,
    description: str,
    amounts: list[Amount],
    document: Source,
    event: str,
    actor: User | None,
) -> JournalEntry | None:
    return ledger.post(
        session,
        entry_date=ledger.shop_day(at),
        description=description,
        amounts=amounts,
        source=EntrySource.document,
        actor=actor,
        document=document,
        event=event,
    )


def _paid_from(session: Session, account_id: int | None) -> int:
    """A Goods Receipt paid at once, before slice 5 knew from where: Kas
    Besar."""
    return account_id or ledger.account_of(session, AccountRole.cash_main)


def _supplier_name(session: Session, supplier_id: int) -> str:
    supplier = session.get(Supplier, supplier_id)
    return supplier.name if supplier else ''


# Stock documents


def goods_receipt(
    session: Session, receipt: GoodsReceipt, *, actor: User | None
) -> None:
    """Persediaan against Hutang Usaha, or the account it was paid from."""
    assert receipt.id is not None and receipt.number and receipt.completed_at
    if receipt.payment_status == PaymentStatus.paid:
        payer = Amount(
            _paid_from(session, receipt.paid_from_account_id),
            -receipt.total_cost,
        )
    else:
        payer = Amount(
            ledger.account_of(session, AccountRole.accounts_payable),
            -receipt.total_cost,
            supplier_id=receipt.supplier_id,
        )
    _post(
        session,
        at=receipt.completed_at,
        description=(
            f'Barang masuk {receipt.number} dari '
            f'{_supplier_name(session, receipt.supplier_id)}'
        ),
        amounts=[
            *_stock(session, _movements(session, 'goods_receipt', receipt.id)),
            payer,
        ],
        document=Source('goods_receipt', receipt.id, receipt.number),
        event='complete',
        actor=actor,
    )


def production_receipt(
    session: Session, receipt: ProductionReceipt, *, actor: User | None
) -> None:
    """Persediaan against Biaya Produksi Dibebankan, which the Cash-outs
    for fabric and tailoring are booked to."""
    assert receipt.id is not None and receipt.number and receipt.completed_at
    _post(
        session,
        at=receipt.completed_at,
        description=f'Hasil produksi {receipt.number}',
        amounts=[
            *_stock(
                session, _movements(session, 'production_receipt', receipt.id)
            ),
            Amount(
                ledger.account_of(session, AccountRole.production_cost),
                -receipt.total_cost,
            ),
        ],
        document=Source('production_receipt', receipt.id, receipt.number),
        event='complete',
        actor=actor,
    )


def supplier_return(
    session: Session, supplier_return: SupplierReturn, *, actor: User | None
) -> None:
    """Hutang Usaha (or the account the receipt was paid from) at the
    receipt's cost, Persediaan at stock cost, the difference to Harga Pokok
    Penjualan."""
    assert supplier_return.id is not None and supplier_return.number
    assert supplier_return.completed_at is not None
    receipt = session.get(GoodsReceipt, supplier_return.goods_receipt_id)
    assert receipt is not None
    if receipt.payment_status == PaymentStatus.paid:
        refund = Amount(
            _paid_from(session, receipt.paid_from_account_id),
            supplier_return.total_refund,
        )
    else:
        refund = Amount(
            ledger.account_of(session, AccountRole.accounts_payable),
            supplier_return.total_refund,
            supplier_id=supplier_return.supplier_id,
        )
    stock = _stock(
        session, _movements(session, 'supplier_return', supplier_return.id)
    )
    stock_value = sum((amount.amount for amount in stock), ZERO)
    difference = Amount(
        ledger.account_of(session, AccountRole.cogs),
        -(supplier_return.total_refund + stock_value),
    )
    _post(
        session,
        at=supplier_return.completed_at,
        description=(
            f'Retur pembelian {supplier_return.number} ke '
            f'{_supplier_name(session, supplier_return.supplier_id)}'
        ),
        amounts=[*stock, refund, difference],
        document=Source(
            'supplier_return', supplier_return.id, supplier_return.number
        ),
        event='complete',
        actor=actor,
    )


def stock_opname(
    session: Session, opname: StockOpname, *, actor: User | None
) -> None:
    """Each Variance against Persediaan. A Surplus is Selisih Lebih
    Persediaan (Saldo Awal for the Opening Opname); a Shortage is Selisih
    Kurang Persediaan, less what an employee is charged, which is Piutang
    Karyawan. A charge above the Shortage's cost is Pendapatan Lain."""
    from opname360.services.opnames import charge_amount

    assert opname.id is not None and opname.approved_at is not None
    lines = {
        line.sku_id: line
        for line in session.exec(
            select(OpnameLine).where(OpnameLine.opname_id == opname.id)
        ).all()
    }
    surplus = ledger.account_of(
        session,
        AccountRole.opening_balance
        if opname.is_opening
        else AccountRole.inventory_surplus,
    )
    shortage = ledger.account_of(session, AccountRole.inventory_shortage)
    receivable = ledger.account_of(session, AccountRole.employee_receivable)
    other_income = ledger.account_of(session, AccountRole.other_income)
    movements = _movements(session, 'stock_opname', opname.id)
    amounts = _stock(session, movements)
    for movement in movements:
        if movement.quantity > 0:
            amounts.append(Amount(surplus, -movement.value))
        elif movement.quantity < 0:
            line = lines[movement.sku_id]
            lost = -movement.value
            charged = ZERO
            if line.resolution == Resolution.employee_charge:
                charged = Decimal(charge_amount(line, movement.value))
                amounts.append(
                    Amount(receivable, charged, user_id=line.charged_user_id)
                )
            rest = lost - charged
            amounts.append(
                Amount(shortage if rest > 0 else other_income, rest)
            )
    _post(
        session,
        at=opname.approved_at,
        description=(
            f'{"Opname awal" if opname.is_opening else "Stok opname"} '
            f'{opname.number}'
        ),
        amounts=amounts,
        document=Source('stock_opname', opname.id, opname.number),
        event='approve',
        actor=actor,
    )


# Backfill


def backfill(session: Session) -> int:
    """Rule 5: post every document completed before the Ledger was switched
    on, in the order it happened and dated when it happened. Whatever is
    already posted is left alone, so it can run again. Returns how many
    entries were written."""
    settings = session.get(ShopSettings, 1)
    if settings and settings.lock_date is not None:
        raise ConflictError(
            'Pembukuan sudah pernah ditutup; pengisian otomatis hanya untuk '
            'awal pembukuan.'
        )
    before = _entry_count(session)
    events: list[tuple[datetime, int, Callable[[], object]]] = []

    def add(at: datetime | None, run: Callable[[], object]) -> None:
        if at is not None:
            events.append((at, len(events), run))

    for document in session.exec(
        select(GoodsReceipt).where(GoodsReceipt.status != DocumentStatus.draft)
    ).all():
        add(
            document.completed_at,
            lambda r=document: goods_receipt(session, r, actor=None),
        )
    for document in session.exec(
        select(ProductionReceipt).where(
            ProductionReceipt.status != DocumentStatus.draft
        )
    ).all():
        add(
            document.completed_at,
            lambda r=document: production_receipt(session, r, actor=None),
        )
    for item in session.exec(
        select(SupplierReturn).where(
            SupplierReturn.status != DocumentStatus.draft
        )
    ).all():
        add(
            item.completed_at,
            lambda r=item: supplier_return(session, r, actor=None),
        )
    for opname in session.exec(
        select(StockOpname).where(
            col(StockOpname.status).in_(
                [OpnameStatus.approved, OpnameStatus.reversed]
            )
        )
    ).all():
        add(
            opname.approved_at,
            lambda o=opname: stock_opname(session, o, actor=None),
        )
    for sale in session.exec(select(Receipt)).all():
        add(sale.created_at, lambda r=sale: receipt(session, r, actor=None))
    for shift in session.exec(select(Shift)).all():
        add(
            shift.opened_at, lambda s=shift: shift_open(session, s, actor=None)
        )
        add(
            shift.closed_at,
            lambda s=shift: shift_close(session, s, actor=None),
        )
        add(
            shift.resolved_at,
            lambda s=shift: shift_resolve(session, s, actor=None),
        )
    for reversal in session.exec(select(Reversal)).all():
        add(
            reversal.created_at,
            lambda r=reversal: ledger.mirror_document(
                session,
                document_type=r.document_type,
                document_id=r.document_id,
                reversal_number=r.number,
                actor=None,
                on=ledger.shop_day(r.created_at),
            ),
        )
    for _, _, run in sorted(events, key=lambda event: (event[0], event[1])):
        run()
    session.commit()
    return _entry_count(session) - before


def _entry_count(session: Session) -> int:
    return session.exec(select(func.count()).select_from(JournalEntry)).one()


# The till


def _method_accounts(session: Session) -> dict[int, int]:
    """Where each Payment Method's money goes: cash into the drawer,
    anything else into its own account, Bank unless the Owner chose one."""
    drawer = ledger.account_of(session, AccountRole.cash_drawer)
    bank = ledger.account_of(session, AccountRole.bank)
    return {
        method.id or 0: drawer
        if method.is_cash
        else (method.account_id or bank)
        for method in session.exec(select(PaymentMethod)).all()
    }


def receipt(session: Session, receipt: Receipt, *, actor: User | None) -> None:
    """A sale, return or exchange: Penjualan at price times quantity,
    Diskon Penjualan and Retur Penjualan, each payment to its account; the
    goods against Persediaan at cost, Harga Pokok Penjualan except a Damaged
    Return's write-off, which is Barang Rusak."""
    assert receipt.id is not None
    lines = session.exec(
        select(ReceiptLine).where(ReceiptLine.receipt_id == receipt.id)
    ).all()
    payments = session.exec(
        select(Payment).where(Payment.receipt_id == receipt.id)
    ).all()
    sold = [line for line in lines if line.quantity > 0]
    returned = [line for line in lines if line.quantity < 0]
    accounts = _method_accounts(session)
    amounts = [
        Amount(
            ledger.account_of(session, AccountRole.sales),
            -Decimal(sum(line.line_total + line.discount for line in sold)),
        ),
        Amount(
            ledger.account_of(session, AccountRole.sales_discount),
            Decimal(sum(line.discount for line in sold)),
        ),
        Amount(
            ledger.account_of(session, AccountRole.sales_return),
            -Decimal(sum(line.line_total for line in returned)),
        ),
        *(
            Amount(
                accounts[payment.payment_method_id], Decimal(payment.amount)
            )
            for payment in payments
        ),
    ]
    inventory = ledger.account_of(session, AccountRole.inventory)
    cogs = ledger.account_of(session, AccountRole.cogs)
    damaged = ledger.account_of(session, AccountRole.damaged_goods)
    for movement in _movements(session, 'receipt', receipt.id):
        amounts.append(Amount(inventory, movement.value))
        counter = (
            damaged if movement.reason == MovementReason.write_off else cogs
        )
        amounts.append(Amount(counter, -movement.value))
    kind = {
        ReceiptKind.sale: 'Penjualan',
        ReceiptKind.return_: 'Retur penjualan',
        ReceiptKind.exchange: 'Tukar tambah',
    }[receipt.kind]
    _post(
        session,
        at=receipt.created_at,
        description=f'{kind} {receipt.number}',
        amounts=amounts,
        document=Source('receipt', receipt.id, receipt.number),
        event='complete',
        actor=actor,
    )


def shift_open(session: Session, shift: Shift, *, actor: User | None) -> None:
    """The float goes from Kas Besar into the drawer."""
    assert shift.id is not None
    _post(
        session,
        at=shift.opened_at,
        description=f'Modal kas shift {shift.number}',
        amounts=[
            Amount(
                ledger.account_of(session, AccountRole.cash_drawer),
                Decimal(shift.opening_float),
            ),
            Amount(
                ledger.account_of(session, AccountRole.cash_main),
                Decimal(-shift.opening_float),
            ),
        ],
        document=Source('shift', shift.id, shift.number),
        event='open',
        actor=actor,
    )


def shift_close(session: Session, shift: Shift, *, actor: User | None) -> None:
    """All the cash counted goes to Kas Besar and the drawer is empty again
    (rule 8); a difference is Selisih Kurang Kas or Selisih Lebih Kas."""
    assert shift.id is not None and shift.closed_at is not None
    assert shift.expected_cash is not None and shift.counted_cash is not None
    variance = shift.counted_cash - shift.expected_cash
    _post(
        session,
        at=shift.closed_at,
        description=f'Tutup shift {shift.number}',
        amounts=[
            Amount(
                ledger.account_of(session, AccountRole.cash_main),
                Decimal(shift.counted_cash),
            ),
            Amount(
                ledger.account_of(session, AccountRole.cash_drawer),
                Decimal(-shift.expected_cash),
            ),
            Amount(
                ledger.account_of(
                    session,
                    AccountRole.cash_over
                    if variance > 0
                    else AccountRole.cash_short,
                ),
                Decimal(-variance),
            ),
        ],
        document=Source('shift', shift.id, shift.number),
        event='close',
        actor=actor,
    )


def shift_resolve(
    session: Session, shift: Shift, *, actor: User | None
) -> None:
    """A short drawer charged to an employee: Piutang Karyawan instead of
    Selisih Kurang Kas. A Company Loss posts nothing more."""
    assert shift.id is not None and shift.resolved_at is not None
    if shift.resolution != Resolution.employee_charge:
        return
    shortage = Decimal(-(shift.cash_variance or 0))
    _post(
        session,
        at=shift.resolved_at,
        description=f'Ganti rugi selisih kas shift {shift.number}',
        amounts=[
            Amount(
                ledger.account_of(session, AccountRole.employee_receivable),
                shortage,
                user_id=shift.charged_user_id,
            ),
            Amount(
                ledger.account_of(session, AccountRole.cash_short), -shortage
            ),
        ],
        document=Source('shift', shift.id, shift.number),
        event='resolve',
        actor=actor,
    )
