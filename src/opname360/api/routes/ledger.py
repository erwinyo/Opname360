from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from opname360.api.deps import AdminDep, SessionDep, require_admin
from opname360.models import (
    AccountBook,
    AccountBookFilter,
    AccountPublic,
    AccountSave,
    JournalEntryPublic,
    JournalFilter,
    JournalPage,
    ManualEntryIn,
    ReversalCreate,
    TrialBalance,
)
from opname360.services import ledger


# Rule 15: the Owner and the Admin keep the books; a Cashier sees none.
router = APIRouter(
    prefix='/ledger', tags=['ledger'], dependencies=[Depends(require_admin)]
)

AccountId = Annotated[int, Path(ge=1)]
EntryId = Annotated[int, Path(ge=1)]


@router.get('/accounts')
def list_accounts(session: SessionDep) -> list[AccountPublic]:
    return ledger.list_accounts(session)


@router.post('/accounts', status_code=status.HTTP_201_CREATED)
def create_account(
    session: SessionDep, data: AccountSave, actor: AdminDep
) -> AccountPublic:
    account = ledger.create_account(session, data, actor=actor)
    return ledger.account_public(session, account)


@router.put('/accounts/{account_id}')
def update_account(
    session: SessionDep,
    account_id: AccountId,
    data: AccountSave,
    actor: AdminDep,
) -> AccountPublic:
    account = ledger.get_account(session, account_id)
    account = ledger.update_account(session, account, data, actor=actor)
    return ledger.account_public(session, account)


@router.delete(
    '/accounts/{account_id}', status_code=status.HTTP_204_NO_CONTENT
)
def delete_account(
    session: SessionDep, account_id: AccountId, actor: AdminDep
) -> None:
    ledger.delete_account(
        session, ledger.get_account(session, account_id), actor=actor
    )


@router.get('/accounts/{account_id}/book')
def read_account_book(
    session: SessionDep,
    account_id: AccountId,
    period: Annotated[AccountBookFilter, Query()],
) -> AccountBook:
    account = ledger.get_account(session, account_id)
    return ledger.account_book(session, account, period.start, period.end)


@router.get('/journal')
def list_entries(
    session: SessionDep, filters: Annotated[JournalFilter, Query()]
) -> JournalPage:
    return ledger.list_entries(session, filters)


@router.post('/journal', status_code=status.HTTP_201_CREATED)
def create_manual_entry(
    session: SessionDep, data: ManualEntryIn, actor: AdminDep
) -> JournalEntryPublic:
    entry = ledger.create_manual(session, data, actor=actor)
    return ledger.entry_public(session, entry)


@router.get('/journal/{entry_id}')
def read_entry(session: SessionDep, entry_id: EntryId) -> JournalEntryPublic:
    return ledger.entry_public(session, ledger.get_entry(session, entry_id))


@router.post('/journal/{entry_id}/reverse')
def reverse_entry(
    session: SessionDep,
    entry_id: EntryId,
    data: ReversalCreate,
    actor: AdminDep,
) -> JournalEntryPublic:
    entry = ledger.get_entry(session, entry_id)
    mirror = ledger.reverse_entry(session, entry, data.reason, actor=actor)
    return ledger.entry_public(session, mirror)


@router.get('/trial-balance')
def trial_balance(
    session: SessionDep, on: Annotated[date, Query()]
) -> TrialBalance:
    return ledger.trial_balance(session, on)
