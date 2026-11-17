"""Slice 5, rules 3-6: stock documents in the Ledger, and backfill."""

from datetime import timedelta
from decimal import Decimal

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from .conftest import (
    OPNAMES,
    account_balance,
    make_user,
    new_receipt,
    new_sku,
    new_supplier,
    open_shift,
    posted,
    receipt_line,
    receive,
    sell,
    stock_value,
)
from .test_opening_opname import counted_opening, with_import_cost
from .test_opname_approval import approve, resolve, reviewed
from .test_supplier_returns import new_return

from opname360.models import (
    Account,
    GoodsReceipt,
    JournalEntry,
    JournalLine,
    Role,
    Sku,
    User,
)
from opname360.services import posting
from opname360.services.documents import shop_now


RECEIPTS = '/api/v1/goods-receipts/'
PRODUCTION = '/api/v1/production-receipts/'


def bank_id(session: Session) -> int:
    bank = session.exec(select(Account).where(Account.name == 'Bank')).one()
    assert bank.id is not None
    return bank.id


# Rule 4: each row of the postings table, by a worked example.


def test_a_goods_receipt_paid_or_owed(
    owner_client: TestClient, session: Session
) -> None:
    shirt = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    cash = new_receipt(
        owner_client, supplier['id'], [receipt_line(shirt.id, 10, 5000)]
    )
    assert cash['paid_from_name'] == 'Kas Besar'
    assert posted(session, 'goods_receipt', cash['id']) == {
        'Persediaan': 50000,
        'Kas Besar': -50000,
    }
    by_bank = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 2, 5000)],
        paid_from_account_id=bank_id(session),
    )
    assert posted(session, 'goods_receipt', by_bank['id']) == {
        'Persediaan': 10000,
        'Bank': -10000,
    }
    owed = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 4, 6000)],
        payment_status='owed',
    )
    assert owed['paid_from_name'] is None
    assert posted(session, 'goods_receipt', owed['id']) == {
        'Persediaan': 24000,
        'Hutang Usaha': -24000,
    }
    [line] = session.exec(
        select(JournalLine)
        .join(JournalEntry)
        .where(
            JournalEntry.document_id == owed['id'],
            JournalEntry.document_type == 'goods_receipt',
            JournalLine.credit > 0,
        )
    ).all()
    assert line.supplier_id == supplier['id']


def test_the_drawer_and_non_cash_accounts_cannot_pay_a_supplier(
    owner_client: TestClient, session: Session
) -> None:
    shirt = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    drawer = session.exec(
        select(Account).where(Account.name == 'Kas Kasir')
    ).one()
    stock_account = session.exec(
        select(Account).where(Account.name == 'Persediaan')
    ).one()
    for account in (drawer, stock_account):
        response = owner_client.post(
            RECEIPTS,
            json={
                'supplier_id': supplier['id'],
                'received_on': '2026-11-15',
                'paid_from_account_id': account.id,
                'lines': [receipt_line(shirt.id, 1, 1000)],
            },
        )
        assert response.status_code == 409, account.name


def test_negative_stock_filled_puts_the_cost_difference_in_cogs(
    owner_client: TestClient, session: Session
) -> None:
    """3 pens sold at their last cost of Rp 2.000, then bought at 2.500."""
    pen = new_sku(owner_client, session, selling_price=3500)
    pen.latest_unit_cost = Decimal(2000)
    session.add(pen)
    session.commit()
    open_shift(owner_client)
    assert sell(owner_client, (pen, 3)).status_code == 201
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(pen.id, 10, 2500)],
        payment_status='owed',
    )
    assert posted(session, 'goods_receipt', receipt['id']) == {
        'Persediaan': 23500,
        'Harga Pokok Penjualan': 1500,
        'Hutang Usaha': -25000,
    }


def test_a_production_receipt(
    owner_client: TestClient, session: Session
) -> None:
    shirt = new_sku(owner_client, session)
    response = owner_client.post(
        PRODUCTION,
        json={
            'produced_on': '2026-11-15',
            'lines': [
                {'sku_id': shirt.id, 'quantity': 20, 'unit_cost': 35000}
            ],
        },
    )
    receipt = owner_client.post(
        f'{PRODUCTION}{response.json()["id"]}/complete'
    ).json()
    assert posted(session, 'production_receipt', receipt['id']) == {
        'Persediaan': 700000,
        'Biaya Produksi Dibebankan': -700000,
    }


def test_a_supplier_return_at_the_receipts_cost(
    owner_client: TestClient, session: Session
) -> None:
    """Bought at 5.000 and 7.000: stock is at 6.000 when 2 go back."""
    shirt = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    first = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 5000)],
        payment_status='owed',
    )
    new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 7000)],
        payment_status='owed',
    )
    returned = new_return(owner_client, first, [2]).json()
    assert posted(session, 'supplier_return', returned['id']) == {
        'Hutang Usaha': 10000,
        'Persediaan': -12000,
        'Harga Pokok Penjualan': 2000,
    }
    # From a receipt paid in cash, the money comes back to that account.
    paid = new_receipt(
        owner_client, supplier['id'], [receipt_line(shirt.id, 5, 6000)]
    )
    returned = new_return(owner_client, paid, [1]).json()
    assert posted(session, 'supplier_return', returned['id']) == {
        'Kas Besar': 6000,
        'Persediaan': -6000,
    }


def test_opname_shortages_and_surpluses(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    lost, charged, overcharged, found = (
        new_sku(owner_client, session) for _ in range(4)
    )
    for sku in (lost, charged, overcharged, found):
        receive(owner_client, sku, 5, 1000)
    joko = make_user(session, 'joko', Role.cashier)
    opname, lines = reviewed(
        owner_client,
        session,
        owner,
        {lost.id: 4, charged.id: 3, overcharged.id: 4, found.id: 6},
    )
    resolve(owner_client, opname, lines[lost.id], shortage_reason='lost')
    resolve(
        owner_client,
        opname,
        lines[charged.id],
        shortage_reason='lost',
        resolution='employee_charge',
        charged_user_id=joko.id,
        # Half of the Rp 2.000 it cost.
        charge_amount=1000,
    )
    resolve(
        owner_client,
        opname,
        lines[overcharged.id],
        shortage_reason='lost',
        resolution='employee_charge',
        charged_user_id=joko.id,
        # Charged at the selling price, above the Rp 1.000 it cost.
        charge_amount=1500,
    )
    assert approve(owner_client, opname).status_code == 200
    assert posted(session, 'stock_opname', opname['id']) == {
        'Persediaan': -3000,
        'Selisih Kurang Persediaan': 2000,
        'Piutang Karyawan': 2500,
        'Pendapatan Lain': -500,
        'Selisih Lebih Persediaan': -1000,
    }
    [receivable] = session.exec(
        select(JournalLine)
        .join(Account)
        .where(Account.name == 'Piutang Karyawan')
    ).all()
    assert receivable.user_id == joko.id


def test_the_opening_opname_is_opening_balance(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    sku = new_sku(owner_client, session)
    with_import_cost(session, sku, 4500)
    opname = counted_opening(owner_client, session, owner, {sku.id: 10})
    response = owner_client.post(f'{OPNAMES}{opname["id"]}/approve')
    assert response.status_code == 200, response.text
    assert posted(session, 'stock_opname', opname['id']) == {
        'Persediaan': 45000,
        'Saldo Awal': -45000,
    }


def test_a_reversal_mirrors_the_entry_today(
    owner_client: TestClient, session: Session
) -> None:
    """Rule 2."""
    shirt = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 3, 5000)],
        payment_status='owed',
    )
    response = owner_client.post(
        f'{RECEIPTS}{receipt["id"]}/reverse', json={'reason': 'Salah pemasok'}
    )
    assert response.status_code == 200, response.text
    mirror = posted(
        session, 'goods_receipt', receipt['id'], 'reverse-complete'
    )
    assert mirror == {'Persediaan': -15000, 'Hutang Usaha': 15000}
    assert posted(session, 'goods_receipt', receipt['id']) == {}
    entry = session.exec(
        select(JournalEntry).where(JournalEntry.event == 'reverse-complete')
    ).one()
    assert entry.entry_date == shop_now().date()
    assert entry.reverses_id is not None


def test_completing_and_posting_go_together(
    owner_client: TestClient,
    session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule 3: if posting fails, the document isn't completed either."""
    shirt = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    draft = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 3, 5000)],
        complete=False,
    )

    def broken(*args: object, **kwargs: object) -> None:
        raise RuntimeError('Ledger down')

    monkeypatch.setattr(posting, 'goods_receipt', broken)
    with pytest.raises(RuntimeError):
        owner_client.post(f'{RECEIPTS}{draft["id"]}/complete')
    session.rollback()
    receipt = session.get(GoodsReceipt, draft['id'])
    assert receipt is not None
    session.refresh(receipt)
    assert receipt.status == 'draft'
    assert stock_value(session) == 0


def test_backfill_posts_history_once_and_persediaan_equals_stock(
    owner_client: TestClient, session: Session, owner: User
) -> None:
    """Rules 5 and 6."""
    shirt = new_sku(owner_client, session)
    hat = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    old = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 10, 5000), receipt_line(hat.id, 4, 2500)],
        payment_status='owed',
    )
    new_return(owner_client, old, [2])
    opname, lines = reviewed(owner_client, session, owner, {hat.id: 3})
    resolve(owner_client, opname, lines[hat.id], shortage_reason='damaged')
    approve(owner_client, opname)
    reversed_receipt = new_receipt(
        owner_client, supplier['id'], [receipt_line(shirt.id, 1, 5000)]
    )
    owner_client.post(
        f'{RECEIPTS}{reversed_receipt["id"]}/reverse', json={'reason': 'Dobel'}
    )
    # As if all of it happened three days ago, before the Ledger existed.
    three_days_ago = shop_now() - timedelta(days=3)
    receipt = session.get(GoodsReceipt, old['id'])
    assert receipt is not None
    receipt.completed_at = three_days_ago
    session.add(receipt)
    expected = {
        (entry.document_type, entry.document_id, entry.event)
        for entry in session.exec(select(JournalEntry)).all()
    }
    session.exec(delete(JournalLine))  # ty: ignore[no-matching-overload]
    session.exec(delete(JournalEntry))  # ty: ignore[no-matching-overload]
    session.commit()
    assert account_balance(session, 'Persediaan') == 0

    written = posting.backfill(session)

    assert written == len(expected) == 5
    entries = session.exec(select(JournalEntry)).all()
    assert {
        (entry.document_type, entry.document_id, entry.event)
        for entry in entries
    } == expected
    first = next(
        e
        for e in entries
        if e.document_id == old['id'] and e.document_type == 'goods_receipt'
    )
    assert first.entry_date == three_days_ago.date()
    assert account_balance(session, 'Persediaan') == stock_value(session)
    assert posting.backfill(session) == 0

    # And it stays equal with every later document.
    receive(owner_client, hat, 7, 3000)
    assert account_balance(session, 'Persediaan') == stock_value(session)


def test_receipts_list_who_paid(
    owner_client: TestClient, session: Session
) -> None:
    shirt: Sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client,
        supplier['id'],
        [receipt_line(shirt.id, 1, 1000)],
        paid_from_account_id=bank_id(session),
    )
    read = owner_client.get(f'{RECEIPTS}{receipt["id"]}').json()
    assert read['paid_from_name'] == 'Bank'
