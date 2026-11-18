"""Money that isn't a sale (slice 5, step 4): Cash-outs, cash transfers,
supplier payments and debts, settling Employee Charges, opening balances."""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlmodel import Session, col, func, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.models import (
    Account,
    AccountRole,
    CashFilter,
    CashOut,
    CashOutCreate,
    CashOutPage,
    CashOutPublic,
    CashTransfer,
    CashTransferCreate,
    CashTransferPage,
    CashTransferPublic,
    ChargeStatus,
    DocumentStatus,
    EmployeeCharge,
    EntrySource,
    GoodsReceipt,
    JournalEntry,
    JournalLine,
    OpeningBalanceIn,
    OwedReceipt,
    PaymentStatus,
    Shift,
    Supplier,
    SupplierDebt,
    SupplierPayment,
    SupplierPaymentCreate,
    SupplierPaymentLine,
    SupplierPaymentLinePublic,
    SupplierPaymentPage,
    SupplierPaymentPublic,
    SupplierReturn,
    User,
)
from opname360.services import activity_log, documents, ledger, stock
from opname360.services.costing import Source
from opname360.services.ledger import Amount


CASH_OUT = 'cash_out'
TRANSFER = 'cash_transfer'
PAYMENT = 'supplier_payment'
CHARGE = 'employee_charge'


def _check_date(session: Session, day: date) -> None:
    if day > ledger.today():
        raise ConflictError('Tanggalnya tidak boleh di masa depan.')
    ledger.check_open(session, day)


def _post(
    session: Session,
    *,
    day: date,
    description: str,
    amounts: list[Amount],
    document: Source,
    actor: User,
    event: str = 'complete',
) -> None:
    ledger.post(
        session,
        entry_date=day,
        description=description,
        amounts=amounts,
        source=EntrySource.document,
        actor=actor,
        document=document,
        event=event,
    )


def _account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None or not account.is_active:
        raise NotFoundError('Akun tidak ditemukan atau tidak aktif.')
    return account


# Kas Keluar


def create_cash_out(
    session: Session, data: CashOutCreate, *, actor: User
) -> CashOut:
    """An expense paid from a cash or bank account. From the drawer it can
    only be today and during an open Shift, whose expected cash it lowers
    (rule 9)."""
    _check_date(session, data.paid_on)
    paid_from = _account(session, data.paid_from_account_id)
    if not paid_from.is_cash:
        raise ConflictError('Bayar dari akun kas atau bank.')
    expense = _account(session, data.expense_account_id)
    if expense.is_cash or expense.role in ledger.SYSTEM_ONLY | {
        AccountRole.opening_balance
    }:
        raise ConflictError(
            f'{expense.name} tidak bisa dipakai untuk kas keluar.'
        )
    shift_id = None
    if paid_from.role == AccountRole.cash_drawer:
        if data.paid_on != ledger.today():
            raise ConflictError(
                'Kas keluar dari laci kasir hanya untuk hari ini.'
            )
        shift = _open_shift(session)
        shift_id = shift.id
    cash_out = CashOut(
        number=documents.next_number(session, 'KK'),
        paid_on=data.paid_on,
        paid_from_account_id=paid_from.id or 0,
        expense_account_id=expense.id or 0,
        amount=data.amount,
        description=data.description.strip(),
        paid_to=(data.paid_to or '').strip() or None,
        shift_id=shift_id,
        created_by=actor.id,
    )
    session.add(cash_out)
    session.flush()
    assert cash_out.id is not None
    _post(
        session,
        day=cash_out.paid_on,
        description=f'Kas keluar {cash_out.number}: {cash_out.description}',
        amounts=[
            Amount(expense.id or 0, Decimal(cash_out.amount)),
            Amount(paid_from.id or 0, Decimal(-cash_out.amount)),
        ],
        document=Source(CASH_OUT, cash_out.id, cash_out.number),
        actor=actor,
    )
    activity_log.record(
        session,
        actor=actor,
        action='cash_out.create',
        summary=(
            f'Kas keluar {cash_out.number} dari {paid_from.name} untuk '
            f'{expense.name}: {cash_out.description}'
        ),
        entity_type=CASH_OUT,
        entity_id=cash_out.id,
    )
    session.commit()
    return cash_out


def _open_shift(session: Session) -> Shift:
    location_id = stock.resolve_location(session, None)
    shift = session.exec(
        select(Shift).where(
            Shift.location_id == location_id, col(Shift.closed_at).is_(None)
        )
    ).first()
    if shift is None:
        raise ConflictError(
            'Tidak ada shift yang buka; kas keluar dari laci kasir hanya '
            'saat shift berjalan.'
        )
    return shift


def reverse_cash_out(
    session: Session, cash_out: CashOut, reason: str, *, actor: User
) -> CashOut:
    cash_out = documents.lock(session, CashOut, cash_out.id or 0)
    if cash_out.shift_id is not None:
        shift = session.get(Shift, cash_out.shift_id)
        if shift is not None and shift.closed_at is not None:
            raise ConflictError(
                'Shiftnya sudah ditutup, jadi kas keluar dari laci ini tidak '
                'bisa dibatalkan.'
            )
    documents.reverse(
        session,
        cash_out,
        document_type=CASH_OUT,
        label=f'kas keluar {cash_out.number}',
        reason=reason,
        actor=actor,
    )
    session.commit()
    return cash_out


def drawer_cash_outs(session: Session, shift: Shift) -> int:
    """What a Shift paid out of the drawer."""
    return int(
        session.exec(
            select(func.coalesce(func.sum(CashOut.amount), 0)).where(
                CashOut.shift_id == shift.id,
                CashOut.status == DocumentStatus.completed,
            )
        ).one()
    )


def get_cash_out(session: Session, cash_out_id: int) -> CashOut:
    cash_out = session.get(CashOut, cash_out_id)
    if cash_out is None:
        raise NotFoundError('Kas keluar tidak ditemukan.')
    return cash_out


def cash_out_public(session: Session, cash_out: CashOut) -> CashOutPublic:
    shift = (
        session.get(Shift, cash_out.shift_id) if cash_out.shift_id else None
    )
    return CashOutPublic.model_validate(
        cash_out,
        update={
            'paid_from_name': ledger.account_name(
                session, cash_out.paid_from_account_id
            ),
            'expense_name': ledger.account_name(
                session, cash_out.expense_account_id
            ),
            'shift_number': shift.number if shift else None,
            'created_by_name': documents.user_name(
                session, cash_out.created_by
            ),
            'reversal': documents.reversal_public(
                session, CASH_OUT, cash_out.id or 0
            ),
        },
    )


def list_cash_outs(session: Session, filters: CashFilter) -> CashOutPage:
    conditions = _period(CashOut.paid_on, filters)
    total = session.exec(
        select(func.count()).select_from(CashOut).where(*conditions)
    ).one()
    rows = session.exec(
        select(CashOut)
        .where(*conditions)
        .order_by(col(CashOut.paid_on).desc(), col(CashOut.id).desc())
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return CashOutPage(
        items=[cash_out_public(session, row) for row in rows], total=total
    )


def _period(column: Any, filters: CashFilter) -> list[Any]:
    conditions = []
    if filters.start is not None:
        conditions.append(col(column) >= filters.start)
    if filters.end is not None:
        conditions.append(col(column) <= filters.end)
    return conditions


# Pindah Kas


def create_transfer(
    session: Session, data: CashTransferCreate, *, actor: User
) -> CashTransfer:
    """Between cash and bank accounts, e.g. depositing at the bank. The
    drawer only fills and empties with its Shift."""
    _check_date(session, data.transferred_on)
    accounts = [
        _account(session, data.from_account_id),
        _account(session, data.to_account_id),
    ]
    for account in accounts:
        if not account.is_cash or account.role == AccountRole.cash_drawer:
            raise ConflictError(
                f'{account.name} tidak bisa dipakai untuk pindah kas.'
            )
    paying, receiving = accounts
    transfer = CashTransfer(
        number=documents.next_number(session, 'PK'),
        transferred_on=data.transferred_on,
        from_account_id=paying.id or 0,
        to_account_id=receiving.id or 0,
        amount=data.amount,
        description=(data.description or '').strip() or None,
        created_by=actor.id,
    )
    session.add(transfer)
    session.flush()
    assert transfer.id is not None
    _post(
        session,
        day=transfer.transferred_on,
        description=(
            f'Pindah kas {transfer.number} dari {paying.name} ke '
            f'{receiving.name}'
        ),
        amounts=[
            Amount(receiving.id or 0, Decimal(transfer.amount)),
            Amount(paying.id or 0, Decimal(-transfer.amount)),
        ],
        document=Source(TRANSFER, transfer.id, transfer.number),
        actor=actor,
    )
    activity_log.record(
        session,
        actor=actor,
        action='cash_transfer.create',
        summary=f'Pindah kas {transfer.number} dari {paying.name} ke {receiving.name}.',
        entity_type=TRANSFER,
        entity_id=transfer.id,
    )
    session.commit()
    return transfer


def get_transfer(session: Session, transfer_id: int) -> CashTransfer:
    transfer = session.get(CashTransfer, transfer_id)
    if transfer is None:
        raise NotFoundError('Pindah kas tidak ditemukan.')
    return transfer


def reverse_transfer(
    session: Session, transfer: CashTransfer, reason: str, *, actor: User
) -> CashTransfer:
    transfer = documents.lock(session, CashTransfer, transfer.id or 0)
    documents.reverse(
        session,
        transfer,
        document_type=TRANSFER,
        label=f'pindah kas {transfer.number}',
        reason=reason,
        actor=actor,
    )
    session.commit()
    return transfer


def transfer_public(
    session: Session, transfer: CashTransfer
) -> CashTransferPublic:
    return CashTransferPublic.model_validate(
        transfer,
        update={
            'from_name': ledger.account_name(
                session, transfer.from_account_id
            ),
            'to_name': ledger.account_name(session, transfer.to_account_id),
            'created_by_name': documents.user_name(
                session, transfer.created_by
            ),
            'reversal': documents.reversal_public(
                session, TRANSFER, transfer.id or 0
            ),
        },
    )


def list_transfers(session: Session, filters: CashFilter) -> CashTransferPage:
    conditions = _period(CashTransfer.transferred_on, filters)
    total = session.exec(
        select(func.count()).select_from(CashTransfer).where(*conditions)
    ).one()
    rows = session.exec(
        select(CashTransfer)
        .where(*conditions)
        .order_by(
            col(CashTransfer.transferred_on).desc(),
            col(CashTransfer.id).desc(),
        )
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return CashTransferPage(
        items=[transfer_public(session, row) for row in rows], total=total
    )


# Supplier debts and payments


def supplier_debts(
    session: Session, supplier_id: int | None = None
) -> list[SupplierDebt]:
    """What is owed per Supplier: each owed Goods Receipt less its returns
    and payments, and any debt entered as an opening balance."""
    receipts = session.exec(
        select(GoodsReceipt)
        .where(
            GoodsReceipt.status == DocumentStatus.completed,
            GoodsReceipt.payment_status == PaymentStatus.owed,
            *(
                [GoodsReceipt.supplier_id == supplier_id]
                if supplier_id is not None
                else []
            ),
        )
        .order_by(col(GoodsReceipt.received_on), col(GoodsReceipt.id))
    ).all()
    returned = _sums(
        session,
        select(
            SupplierReturn.goods_receipt_id,
            func.sum(SupplierReturn.total_refund),
        )
        .where(SupplierReturn.status == DocumentStatus.completed)
        .group_by(col(SupplierReturn.goods_receipt_id)),
    )
    paid = _sums(
        session,
        select(
            SupplierPaymentLine.goods_receipt_id,
            func.sum(SupplierPaymentLine.amount),
        )
        .join(
            SupplierPayment,
            col(SupplierPaymentLine.payment_id) == SupplierPayment.id,
        )
        .where(SupplierPayment.status == DocumentStatus.completed)
        .group_by(col(SupplierPaymentLine.goods_receipt_id)),
    )
    by_supplier: dict[int, list[OwedReceipt]] = defaultdict(list)
    for supplier_id_, owed in _opening_debts(session, supplier_id).items():
        if owed > 0:
            by_supplier[supplier_id_].append(
                OwedReceipt(
                    goods_receipt_id=None,
                    number=None,
                    received_on=None,
                    supplier_invoice=None,
                    total=owed + _opening_paid(session, supplier_id_),
                    returned=0,
                    paid=_opening_paid(session, supplier_id_),
                    owed=owed,
                )
            )
    for receipt in receipts:
        total = _rupiah(receipt.total_cost)
        back = _rupiah(returned.get(receipt.id, Decimal(0)))
        settled = int(paid.get(receipt.id, 0))
        owed = total - back - settled
        if owed <= 0:
            continue
        by_supplier[receipt.supplier_id].append(
            OwedReceipt(
                goods_receipt_id=receipt.id,
                number=receipt.number,
                received_on=receipt.received_on,
                supplier_invoice=receipt.supplier_invoice,
                total=total,
                returned=back,
                paid=settled,
                owed=owed,
            )
        )
    debts = []
    for supplier_id_, rows in by_supplier.items():
        supplier = session.get(Supplier, supplier_id_)
        assert supplier is not None
        debts.append(
            SupplierDebt(
                supplier_id=supplier_id_,
                supplier_name=supplier.name,
                owed=sum(row.owed for row in rows),
                receipts=rows,
            )
        )
    return sorted(debts, key=lambda debt: (-debt.owed, debt.supplier_name))


def _rupiah(amount: Decimal) -> int:
    """Debts are paid in whole rupiah; a receipt's 4-decimal cost rounds."""
    return int(amount.quantize(Decimal(1)))


def _sums(session: Session, query: Any) -> dict[Any, Any]:
    return {key: total for key, total in session.exec(query).all()}


def _opening_debts(
    session: Session, supplier_id: int | None
) -> dict[int, int]:
    """Debts entered as opening balances, less what has been paid on them."""
    payable = ledger.account_of(session, AccountRole.accounts_payable)
    rows = session.exec(
        select(
            JournalLine.supplier_id,
            func.sum(JournalLine.credit - JournalLine.debit),
        )
        .join(JournalEntry, col(JournalLine.entry_id) == JournalEntry.id)
        .where(
            JournalLine.account_id == payable,
            JournalEntry.source == EntrySource.opening,
            col(JournalLine.supplier_id).is_not(None),
            *(
                [JournalLine.supplier_id == supplier_id]
                if supplier_id is not None
                else []
            ),
        )
        .group_by(col(JournalLine.supplier_id))
    ).all()
    return {
        sid: _rupiah(total) - _opening_paid(session, sid)
        for sid, total in rows
        if sid is not None
    }


def _opening_paid(session: Session, supplier_id: int) -> int:
    return int(
        session.exec(
            select(func.coalesce(func.sum(SupplierPaymentLine.amount), 0))
            .join(
                SupplierPayment,
                col(SupplierPaymentLine.payment_id) == SupplierPayment.id,
            )
            .where(
                SupplierPayment.supplier_id == supplier_id,
                SupplierPayment.status == DocumentStatus.completed,
                col(SupplierPaymentLine.goods_receipt_id).is_(None),
            )
        ).one()
    )


def create_payment(
    session: Session, data: SupplierPaymentCreate, *, actor: User
) -> SupplierPayment:
    """Rule 10: each part pays at most what is still owed on it."""
    _check_date(session, data.paid_on)
    supplier = session.get(Supplier, data.supplier_id)
    if supplier is None:
        raise NotFoundError('Pemasok tidak ditemukan.')
    paid_from = ledger.paying_account(session, data.paid_from_account_id)
    # Lock the receipts paid, so two payments can't both pay the same debt.
    for line in data.lines:
        if line.goods_receipt_id is not None:
            documents.lock(session, GoodsReceipt, line.goods_receipt_id)
    owed = {
        row.goods_receipt_id: row.owed
        for debt in supplier_debts(session, supplier.id)
        for row in debt.receipts
    }
    seen: set[int | None] = set()
    for line in data.lines:
        if line.goods_receipt_id in seen:
            raise ConflictError(
                'Satu barang masuk hanya sekali per pembayaran.'
            )
        seen.add(line.goods_receipt_id)
        if line.goods_receipt_id is not None:
            receipt = session.get(GoodsReceipt, line.goods_receipt_id)
            if receipt is None or receipt.supplier_id != supplier.id:
                raise ConflictError('Barang masuk ini bukan dari pemasok ini.')
        limit = owed.get(line.goods_receipt_id, 0)
        if line.amount > limit:
            what = (
                'saldo awal hutang'
                if line.goods_receipt_id is None
                else f'barang masuk {receipt.number}'
            )
            raise ConflictError(
                f'Pembayaran untuk {what} melebihi sisa hutangnya '
                f'({limit:,}).'.replace(',', '.')
            )
    total = sum(line.amount for line in data.lines)
    payment = SupplierPayment(
        number=documents.next_number(session, 'BH'),
        supplier_id=supplier.id or 0,
        paid_on=data.paid_on,
        paid_from_account_id=paid_from,
        amount=total,
        note=(data.note or '').strip() or None,
        created_by=actor.id,
    )
    session.add(payment)
    session.flush()
    assert payment.id is not None
    for line in data.lines:
        session.add(
            SupplierPaymentLine(
                payment_id=payment.id,
                goods_receipt_id=line.goods_receipt_id,
                amount=line.amount,
            )
        )
    _post(
        session,
        day=payment.paid_on,
        description=f'Bayar hutang {payment.number} ke {supplier.name}',
        amounts=[
            Amount(
                ledger.account_of(session, AccountRole.accounts_payable),
                Decimal(total),
                supplier_id=supplier.id,
            ),
            Amount(paid_from, Decimal(-total)),
        ],
        document=Source(PAYMENT, payment.id, payment.number),
        actor=actor,
    )
    activity_log.record(
        session,
        actor=actor,
        action='supplier_payment.create',
        summary=f'Bayar hutang {payment.number} ke {supplier.name}.',
        entity_type=PAYMENT,
        entity_id=payment.id,
    )
    session.commit()
    return payment


def get_payment(session: Session, payment_id: int) -> SupplierPayment:
    payment = session.get(SupplierPayment, payment_id)
    if payment is None:
        raise NotFoundError('Pembayaran hutang tidak ditemukan.')
    return payment


def reverse_payment(
    session: Session, payment: SupplierPayment, reason: str, *, actor: User
) -> SupplierPayment:
    payment = documents.lock(session, SupplierPayment, payment.id or 0)
    documents.reverse(
        session,
        payment,
        document_type=PAYMENT,
        label=f'pembayaran hutang {payment.number}',
        reason=reason,
        actor=actor,
    )
    session.commit()
    return payment


def payment_public(
    session: Session, payment: SupplierPayment
) -> SupplierPaymentPublic:
    supplier = session.get(Supplier, payment.supplier_id)
    lines = []
    for line in payment.lines:
        receipt = (
            session.get(GoodsReceipt, line.goods_receipt_id)
            if line.goods_receipt_id
            else None
        )
        lines.append(
            SupplierPaymentLinePublic(
                goods_receipt_id=line.goods_receipt_id,
                goods_receipt_number=receipt.number if receipt else None,
                amount=line.amount,
            )
        )
    return SupplierPaymentPublic.model_validate(
        payment,
        update={
            'supplier_name': supplier.name if supplier else '',
            'paid_from_name': ledger.account_name(
                session, payment.paid_from_account_id
            ),
            'created_by_name': documents.user_name(
                session, payment.created_by
            ),
            'lines': lines,
            'reversal': documents.reversal_public(
                session, PAYMENT, payment.id or 0
            ),
        },
    )


def list_payments(
    session: Session, filters: CashFilter
) -> SupplierPaymentPage:
    conditions = _period(SupplierPayment.paid_on, filters)
    total = session.exec(
        select(func.count()).select_from(SupplierPayment).where(*conditions)
    ).one()
    rows = session.exec(
        select(SupplierPayment)
        .where(*conditions)
        .order_by(
            col(SupplierPayment.paid_on).desc(), col(SupplierPayment.id).desc()
        )
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return SupplierPaymentPage(
        items=[payment_public(session, row) for row in rows], total=total
    )


# Employee Charges


def settle_charge(
    session: Session,
    charge: EmployeeCharge,
    *,
    by_salary: bool,
    account_id: int | None,
    actor: User,
) -> EmployeeCharge:
    """Paid back in cash (into Kas Besar or another account) or deducted
    from salary (Gaji): either way Piutang Karyawan goes down."""
    charge = documents.lock(session, EmployeeCharge, charge.id or 0)
    if charge.status != ChargeStatus.outstanding:
        raise ConflictError('Ganti rugi ini sudah lunas atau dibatalkan.')
    receiving = (
        ledger.account_of(session, AccountRole.salary)
        if by_salary
        else ledger.paying_account(session, account_id)
    )
    charge.status = ChargeStatus.settled
    charge.settled_at = documents.shop_now()
    charge.settled_by = actor.id
    charge.settled_by_salary = by_salary
    session.add(charge)
    assert charge.id is not None
    employee = documents.user_name(session, charge.user_id)
    _post(
        session,
        day=ledger.today(),
        description=(
            f'Ganti rugi {employee} '
            f'{"dipotong gaji" if by_salary else "dibayar"}: {charge.description}'
        ),
        amounts=[
            Amount(receiving, Decimal(charge.amount)),
            Amount(
                ledger.account_of(session, AccountRole.employee_receivable),
                Decimal(-charge.amount),
                user_id=charge.user_id,
            ),
        ],
        document=Source(CHARGE, charge.id, charge.source_number),
        actor=actor,
        event='settle',
    )
    activity_log.record(
        session,
        actor=actor,
        action='employee_charge.settle',
        summary=(
            f'Ganti rugi {employee} '
            f'{"dipotong gaji" if by_salary else "dibayar"}.'
        ),
        entity_type=CHARGE,
        entity_id=charge.id,
    )
    session.commit()
    return charge


# Saldo Awal


def opening_entry(session: Session) -> JournalEntry | None:
    """The opening balances, unless they were reversed."""
    entries = session.exec(
        select(JournalEntry).where(
            JournalEntry.source == EntrySource.opening,
            col(JournalEntry.reverses_id).is_(None),
        )
    ).all()
    reversed_ids = set(
        session.exec(
            select(JournalEntry.reverses_id).where(
                col(JournalEntry.reverses_id).is_not(None)
            )
        ).all()
    )
    live = [entry for entry in entries if entry.id not in reversed_ids]
    return live[0] if live else None


def enter_opening_balances(
    session: Session, data: OpeningBalanceIn, *, actor: User
) -> JournalEntry:
    """Rule 11: cash, bank, debts and capital on the day the books start,
    once, against Saldo Awal. Stock comes from the Opening Opname."""
    if opening_entry(session) is not None:
        raise ConflictError(
            'Saldo awal sudah diisi; batalkan jurnalnya dulu untuk mengubah.'
        )
    _check_date(session, data.entry_date)
    amounts = ledger.check_lines(session, data.lines, opening=True)
    balance = sum((amount.amount for amount in amounts), Decimal(0))
    amounts.append(
        Amount(
            ledger.account_of(session, AccountRole.opening_balance), -balance
        )
    )
    entry = ledger.post(
        session,
        entry_date=data.entry_date,
        description='Saldo awal pembukuan',
        amounts=amounts,
        source=EntrySource.opening,
        actor=actor,
    )
    if entry is None:
        raise ConflictError('Saldo awal kosong.')
    activity_log.record(
        session,
        actor=actor,
        action='opening_balance.create',
        summary=f'Mengisi saldo awal ({entry.number}).',
        entity_type='journal_entry',
        entity_id=entry.id,
    )
    session.commit()
    return entry
