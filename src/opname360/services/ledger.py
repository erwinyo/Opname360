"""The Ledger's core: accounts, and balanced journal entries that are never
changed (slice 5, rules 1, 2 and 12). What each document posts is in
`posting`."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from opname360.core.errors import ConflictError, NotFoundError
from opname360.models import (
    Account,
    AccountBook,
    AccountBookLine,
    AccountPublic,
    AccountRole,
    AccountSave,
    AccountType,
    EntrySource,
    JournalEntry,
    JournalEntryPublic,
    JournalFilter,
    JournalLine,
    JournalLinePublic,
    JournalPage,
    ManualEntryIn,
    ShopSettings,
    Supplier,
    TrialBalance,
    TrialBalanceRow,
    User,
)
from opname360.services import activity_log, documents
from opname360.services.costing import Source


PREFIX = 'JR'
ZERO = Decimal(0)
# Their balances must match something outside the Ledger (the stock, the
# drawer, the debts per receipt, the charges per employee), so only the
# documents behind them move them.
SYSTEM_ONLY = {
    AccountRole.inventory,
    AccountRole.cash_drawer,
    AccountRole.accounts_payable,
    AccountRole.employee_receivable,
}
DEBIT_NORMAL = {AccountType.asset, AccountType.cogs, AccountType.expense}


@dataclass(frozen=True)
class Amount:
    """One account's share of an entry: above zero a debit, below a credit."""

    account_id: int
    amount: Decimal
    supplier_id: int | None = None
    user_id: int | None = None


def shop_day(moment: datetime) -> date:
    """The Shop Day a moment belongs to."""
    return moment.astimezone(documents.shop_now().tzinfo).date()


def today() -> date:
    return documents.shop_now().date()


def account_of(session: Session, role: AccountRole) -> int:
    """The id of the account playing `role`."""
    account_id = session.exec(
        select(Account.id).where(Account.role == role)
    ).one()
    assert account_id is not None
    return account_id


def lock_date(session: Session) -> date | None:
    settings = session.get(ShopSettings, 1)
    return settings.lock_date if settings else None


def check_open(session: Session, entry_date: date) -> None:
    """Rule 12: nothing is posted on or before the lock date."""
    locked = lock_date(session)
    if locked is not None and entry_date <= locked:
        raise ConflictError(
            f'Pembukuan sampai {locked:%d-%m-%Y} sudah ditutup; '
            'tanggal ini tidak bisa diisi lagi.'
        )


def post(
    session: Session,
    *,
    entry_date: date,
    description: str,
    amounts: Iterable[Amount],
    source: EntrySource,
    actor: User | None,
    document: Source | None = None,
    event: str | None = None,
    reverses: JournalEntry | None = None,
    check_lock: bool = True,
) -> JournalEntry | None:
    """Write one balanced journal entry (rule 1). Amounts on the same
    account and party are netted; an entry that nets to nothing isn't
    written. A document's event is posted once (rule 5)."""
    if document is not None and event is not None:
        existing = session.exec(
            select(JournalEntry).where(
                JournalEntry.document_type == document.type,
                JournalEntry.document_id == document.id,
                JournalEntry.event == event,
            )
        ).first()
        if existing is not None:
            return existing

    netted: dict[tuple[int, int | None, int | None], Decimal] = defaultdict(
        lambda: ZERO
    )
    for item in amounts:
        key = (item.account_id, item.supplier_id, item.user_id)
        netted[key] += item.amount
    lines = {key: amount for key, amount in netted.items() if amount != 0}
    if not lines:
        return None
    difference = sum(lines.values(), ZERO)
    if difference != 0:
        raise ConflictError(
            f'Debit dan kredit tidak seimbang: selisih {difference:,.4f}.'
        )
    if check_lock:
        check_open(session, entry_date)

    entry = JournalEntry(
        number=documents.next_number(session, PREFIX, on=entry_date),
        entry_date=entry_date,
        description=description[:300],
        source=source,
        document_type=document.type if document else None,
        document_id=document.id if document else None,
        document_number=document.number if document else None,
        event=event,
        reverses_id=reverses.id if reverses else None,
        created_by=actor.id if actor else None,
    )
    session.add(entry)
    session.flush()
    assert entry.id is not None
    for (account_id, supplier_id, user_id), amount in sorted(
        lines.items(), key=lambda item: (item[1] < 0, item[0][0])
    ):
        session.add(
            JournalLine(
                entry_id=entry.id,
                account_id=account_id,
                debit=amount if amount > 0 else ZERO,
                credit=-amount if amount < 0 else ZERO,
                supplier_id=supplier_id,
                user_id=user_id,
            )
        )
    session.flush()
    return entry


def amounts_of(entry: JournalEntry) -> list[Amount]:
    return [
        Amount(
            line.account_id,
            line.debit - line.credit,
            line.supplier_id,
            line.user_id,
        )
        for line in entry.lines
    ]


def _mirror(
    session: Session,
    entry: JournalEntry,
    *,
    description: str,
    actor: User,
    event: str | None,
) -> JournalEntry | None:
    """The opposite of `entry`, dated today (rule 2)."""
    return post(
        session,
        entry_date=today(),
        description=description,
        amounts=[
            Amount(a.account_id, -a.amount, a.supplier_id, a.user_id)
            for a in amounts_of(entry)
        ],
        source=entry.source,
        actor=actor,
        document=Source(
            entry.document_type, entry.document_id, entry.document_number or ''
        )
        if entry.document_type and entry.document_id is not None
        else None,
        event=event,
        reverses=entry,
    )


def mirror_document(
    session: Session,
    *,
    document_type: str,
    document_id: int,
    reversal_number: str,
    actor: User,
) -> None:
    """A document's Reversal mirrors every entry the document posted."""
    entries = session.exec(
        select(JournalEntry)
        .where(
            JournalEntry.document_type == document_type,
            JournalEntry.document_id == document_id,
            col(JournalEntry.reverses_id).is_(None),
        )
        .order_by(col(JournalEntry.id))
    ).all()
    for entry in entries:
        _mirror(
            session,
            entry,
            description=f'Pembatalan {entry.description} ({reversal_number})',
            actor=actor,
            event=f'reverse-{entry.event}'[:30],
        )


def reverse_entry(
    session: Session, entry: JournalEntry, reason: str, *, actor: User
) -> JournalEntry:
    """Undo a typed entry (Jurnal Umum or Saldo Awal). A document's entries
    are undone by reversing the document."""
    entry = documents.lock(session, JournalEntry, entry.id or 0)
    if entry.source == EntrySource.document:
        raise ConflictError(
            'Jurnal ini dibuat dari dokumen; batalkan dokumennya.'
        )
    if entry.reverses_id is not None:
        raise ConflictError('Jurnal pembatalan tidak bisa dibatalkan lagi.')
    if _reversed_by(session, entry) is not None:
        raise ConflictError(f'Jurnal {entry.number} sudah dibatalkan.')
    reason = reason.strip()
    if not reason:
        raise ConflictError('Alasan pembatalan wajib diisi.')
    mirror = _mirror(
        session,
        entry,
        description=f'Pembatalan {entry.number}: {reason}',
        actor=actor,
        event=None,
    )
    assert mirror is not None
    activity_log.record(
        session,
        actor=actor,
        action='journal_entry.reverse',
        summary=f'Membatalkan jurnal {entry.number} ({mirror.number}): {reason}',
        entity_type='journal_entry',
        entity_id=entry.id,
    )
    session.commit()
    return mirror


def _reversed_by(session: Session, entry: JournalEntry) -> JournalEntry | None:
    return session.exec(
        select(JournalEntry).where(JournalEntry.reverses_id == entry.id)
    ).first()


# Accounts


def _balances(
    session: Session, *, before: date | None = None
) -> dict[int, tuple[Decimal, Decimal]]:
    """Total debit and credit per account, up to and excluding `before`."""
    query: Any = (
        select(
            JournalLine.account_id,
            func.sum(JournalLine.debit),
            func.sum(JournalLine.credit),
        )
        .join(JournalEntry, col(JournalLine.entry_id) == JournalEntry.id)
        .group_by(col(JournalLine.account_id))
    )
    if before is not None:
        query = query.where(col(JournalEntry.entry_date) < before)
    return {
        account_id: (debit, credit)
        for account_id, debit, credit in session.exec(query).all()
    }


def normal(account: Account, debit_minus_credit: Decimal) -> Decimal:
    """A balance the way the account normally carries it: assets, COGS and
    expenses as debit, the rest as credit."""
    if account.type in DEBIT_NORMAL:
        return debit_minus_credit
    return -debit_minus_credit


def list_accounts(session: Session) -> list[AccountPublic]:
    balances = _balances(session)
    accounts = session.exec(select(Account).order_by(col(Account.code))).all()
    return [
        _account_public(account, balances.get(account.id or 0))
        for account in accounts
    ]


def _account_public(
    account: Account, totals: tuple[Decimal, Decimal] | None
) -> AccountPublic:
    debit, credit = totals or (ZERO, ZERO)
    return AccountPublic.model_validate(
        account,
        update={
            'balance': normal(account, debit - credit),
            'used': bool(totals),
        },
    )


def get_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise NotFoundError('Akun tidak ditemukan.')
    return account


def account_public(session: Session, account: Account) -> AccountPublic:
    return _account_public(account, _balances(session).get(account.id or 0))


def _is_used(session: Session, account: Account) -> bool:
    return (
        session.exec(
            select(JournalLine.id)
            .where(JournalLine.account_id == account.id)
            .limit(1)
        ).first()
        is not None
    )


def _check_unique(
    session: Session, data: AccountSave, account_id: int | None
) -> None:
    clash = session.exec(
        select(Account).where(
            or_(
                Account.code == data.code.strip(),
                Account.name == data.name.strip(),
            ),
            Account.id != account_id,
        )
    ).first()
    if clash is not None:
        raise ConflictError(
            f'Kode atau nama akun sudah dipakai oleh {clash.code} {clash.name}.'
        )


def create_account(
    session: Session, data: AccountSave, *, actor: User
) -> Account:
    _check_unique(session, data, None)
    account = Account(
        code=data.code.strip(),
        name=data.name.strip(),
        type=data.type,
        is_cash=data.is_cash,
        is_active=data.is_active,
    )
    session.add(account)
    session.flush()
    activity_log.record(
        session,
        actor=actor,
        action='account.create',
        summary=f'Menambah akun {account.code} {account.name}.',
        entity_type='account',
        entity_id=account.id,
    )
    session.commit()
    return account


def update_account(
    session: Session, account: Account, data: AccountSave, *, actor: User
) -> Account:
    """Code and name can always change. A system account keeps its type and
    stays active; a used account keeps its type."""
    _check_unique(session, data, account.id)
    if account.role is not None and (
        data.type != account.type
        or data.is_cash != account.is_cash
        or not data.is_active
    ):
        raise ConflictError(
            'Akun ini dipakai sistem: hanya kode dan namanya yang bisa diubah.'
        )
    if data.type != account.type and _is_used(session, account):
        raise ConflictError(
            'Akun ini sudah punya jurnal, jadi jenisnya tidak bisa diubah.'
        )
    account.code = data.code.strip()
    account.name = data.name.strip()
    account.type = data.type
    account.is_cash = data.is_cash
    account.is_active = data.is_active
    session.add(account)
    activity_log.record(
        session,
        actor=actor,
        action='account.update',
        summary=f'Mengubah akun {account.code} {account.name}.',
        entity_type='account',
        entity_id=account.id,
    )
    session.commit()
    return account


def delete_account(session: Session, account: Account, *, actor: User) -> None:
    if account.role is not None:
        raise ConflictError('Akun yang dipakai sistem tidak bisa dihapus.')
    if _is_used(session, account):
        raise ConflictError('Akun ini sudah punya jurnal; nonaktifkan saja.')
    activity_log.record(
        session,
        actor=actor,
        action='account.delete',
        summary=f'Menghapus akun {account.code} {account.name}.',
        entity_type='account',
        entity_id=account.id,
    )
    session.delete(account)
    session.commit()


# Journal entries


def check_lines(
    session: Session, lines: Iterable[Any], *, opening: bool = False
) -> list[Amount]:
    """Typed lines: active accounts the system doesn't keep for itself, and
    a Supplier or employee only where they mean something."""
    amounts = []
    for line in lines:
        account = session.get(Account, line.account_id)
        if account is None or not account.is_active:
            raise ConflictError('Akun tidak ditemukan atau tidak aktif.')
        allowed = {AccountRole.accounts_payable} if opening else set()
        if account.role in SYSTEM_ONLY - allowed:
            raise ConflictError(
                f'{account.name} hanya diisi otomatis dari dokumennya.'
            )
        if account.role == AccountRole.opening_balance and not opening:
            raise ConflictError('Saldo Awal diisi lewat menu Saldo Awal.')
        if line.supplier_id is not None:
            if account.role != AccountRole.accounts_payable:
                raise ConflictError('Pemasok hanya untuk baris Hutang Usaha.')
            if session.get(Supplier, line.supplier_id) is None:
                raise NotFoundError('Pemasok tidak ditemukan.')
        elif account.role == AccountRole.accounts_payable:
            raise ConflictError(
                'Baris Hutang Usaha harus menyebut pemasoknya.'
            )
        if line.user_id is not None:
            raise ConflictError('Karyawan hanya untuk baris Piutang Karyawan.')
        amounts.append(
            Amount(account.id or 0, line.debit - line.credit, line.supplier_id)
        )
    return amounts


def create_manual(
    session: Session, data: ManualEntryIn, *, actor: User
) -> JournalEntry:
    """Jurnal Umum: anything the documents don't cover, such as capital put
    in, withdrawals or depreciation."""
    if data.entry_date > today():
        raise ConflictError('Tanggal jurnal tidak boleh di masa depan.')
    entry = post(
        session,
        entry_date=data.entry_date,
        description=data.description.strip(),
        amounts=check_lines(session, data.lines),
        source=EntrySource.manual,
        actor=actor,
    )
    if entry is None:
        raise ConflictError('Jurnal kosong.')
    activity_log.record(
        session,
        actor=actor,
        action='journal_entry.create',
        summary=f'Membuat jurnal umum {entry.number}: {entry.description}',
        entity_type='journal_entry',
        entity_id=entry.id,
    )
    session.commit()
    return entry


def get_entry(session: Session, entry_id: int) -> JournalEntry:
    entry = session.get(JournalEntry, entry_id)
    if entry is None:
        raise NotFoundError('Jurnal tidak ditemukan.')
    return entry


def list_entries(session: Session, filters: JournalFilter) -> JournalPage:
    conditions: list[Any] = []
    if filters.start is not None:
        conditions.append(col(JournalEntry.entry_date) >= filters.start)
    if filters.end is not None:
        conditions.append(col(JournalEntry.entry_date) <= filters.end)
    if filters.source is not None:
        conditions.append(JournalEntry.source == filters.source)
    if filters.account_id is not None:
        conditions.append(
            col(JournalEntry.id).in_(
                select(JournalLine.entry_id).where(
                    JournalLine.account_id == filters.account_id
                )
            )
        )
    search = (filters.search or '').strip()
    if search:
        conditions.append(
            or_(
                col(JournalEntry.number).icontains(search, autoescape=True),
                col(JournalEntry.description).icontains(
                    search, autoescape=True
                ),
                col(JournalEntry.document_number).icontains(
                    search, autoescape=True
                ),
            )
        )
    total = session.exec(
        select(func.count()).select_from(JournalEntry).where(*conditions)
    ).one()
    entries = session.exec(
        select(JournalEntry)
        .where(*conditions)
        .options(selectinload(JournalEntry.lines))  # ty: ignore[invalid-argument-type]
        .order_by(
            col(JournalEntry.entry_date).desc(), col(JournalEntry.id).desc()
        )
        .offset(filters.offset)
        .limit(filters.limit)
    ).all()
    return JournalPage(
        items=[entry_public(session, entry) for entry in entries], total=total
    )


def entry_public(session: Session, entry: JournalEntry) -> JournalEntryPublic:
    accounts = {
        account.id: account
        for account in session.exec(
            select(Account).where(
                col(Account.id).in_([line.account_id for line in entry.lines])
            )
        ).all()
    }
    reverses = (
        session.get(JournalEntry, entry.reverses_id)
        if entry.reverses_id
        else None
    )
    reversed_by = _reversed_by(session, entry)
    lines = []
    for line in entry.lines:
        account = accounts[line.account_id]
        supplier = (
            session.get(Supplier, line.supplier_id)
            if line.supplier_id
            else None
        )
        lines.append(
            JournalLinePublic(
                id=line.id or 0,
                account_id=line.account_id,
                account_code=account.code,
                account_name=account.name,
                debit=line.debit,
                credit=line.credit,
                supplier_id=line.supplier_id,
                supplier_name=supplier.name if supplier else None,
                user_id=line.user_id,
                user_name=documents.user_name(session, line.user_id),
            )
        )
    return JournalEntryPublic(
        id=entry.id or 0,
        number=entry.number,
        entry_date=entry.entry_date,
        description=entry.description,
        source=entry.source,
        document_type=entry.document_type,
        document_id=entry.document_id,
        document_number=entry.document_number,
        event=entry.event,
        reverses_id=entry.reverses_id,
        reverses_number=reverses.number if reverses else None,
        reversed_by_id=reversed_by.id if reversed_by else None,
        reversed_by_number=reversed_by.number if reversed_by else None,
        created_by_name=documents.user_name(session, entry.created_by),
        created_at=entry.created_at,
        total=sum((line.debit for line in entry.lines), ZERO),
        lines=lines,
    )


# Buku Besar and Neraca Saldo


def account_book(
    session: Session, account: Account, start: date, end: date
) -> AccountBook:
    """One account's entries in a period with a running balance."""
    before = _balances(session, before=start).get(account.id or 0)
    opening = normal(account, before[0] - before[1]) if before else ZERO
    rows = session.exec(
        select(JournalLine, JournalEntry)
        .join(JournalEntry, col(JournalLine.entry_id) == JournalEntry.id)
        .where(
            JournalLine.account_id == account.id,
            col(JournalEntry.entry_date) >= start,
            col(JournalEntry.entry_date) <= end,
        )
        .order_by(
            col(JournalEntry.entry_date),
            col(JournalEntry.id),
            col(JournalLine.id),
        )
    ).all()
    balance = opening
    lines = []
    for line, entry in rows:
        balance += normal(account, line.debit - line.credit)
        lines.append(
            AccountBookLine(
                entry_id=entry.id or 0,
                number=entry.number,
                entry_date=entry.entry_date,
                description=entry.description,
                document_type=entry.document_type,
                document_id=entry.document_id,
                debit=line.debit,
                credit=line.credit,
                balance=balance,
            )
        )
    return AccountBook(
        account=account_public(session, account),
        start=start,
        end=end,
        opening_balance=opening,
        lines=lines,
        total_debit=sum((line.debit for line in lines), ZERO),
        total_credit=sum((line.credit for line in lines), ZERO),
        closing_balance=balance,
    )


def trial_balance(session: Session, on: date) -> TrialBalance:
    """Every account's balance at the end of `on`, on its debit or credit
    side. The two totals are equal because every entry balances."""
    totals = _balances(session, before=on + timedelta(days=1))
    accounts = session.exec(select(Account).order_by(col(Account.code))).all()
    rows = []
    for account in accounts:
        debit, credit = totals.get(account.id or 0, (ZERO, ZERO))
        if debit == credit and not totals.get(account.id or 0):
            continue
        balance = debit - credit
        rows.append(
            TrialBalanceRow(
                account_id=account.id or 0,
                code=account.code,
                name=account.name,
                type=account.type,
                debit=balance if balance > 0 else ZERO,
                credit=-balance if balance < 0 else ZERO,
            )
        )
    return TrialBalance(
        on=on,
        rows=rows,
        total_debit=sum((row.debit for row in rows), ZERO),
        total_credit=sum((row.credit for row in rows), ZERO),
    )
