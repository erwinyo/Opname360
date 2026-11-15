import threading

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from .conftest import (
    make_user,
    new_receipt,
    new_sku,
    new_supplier,
    sign_in,
)
from .database import wipe

from opname360.models import (
    ActivityLog,
    CategoryCreate,
    GoodsReceipt,
    GoodsReceiptLineSave,
    GoodsReceiptSave,
    ProductSave,
    Role,
    SkuSave,
    StockBalance,
    StockMovement,
    SupplierCreate,
    User,
    UserCreate,
)
from opname360.services import catalogue, goods_receipts, suppliers, users


RECEIPTS = '/api/v1/goods-receipts/'


def line(
    sku_id: int | None, quantity: float, unit_cost: float, **more: object
):
    return {
        'sku_id': sku_id,
        'quantity': quantity,
        'unit_cost': unit_cost,
        **more,
    }


def stock_of(session: Session, sku_id: int | None) -> tuple[Decimal, Decimal]:
    balance = session.exec(
        select(StockBalance).where(StockBalance.sku_id == sku_id)
    ).first()
    if balance is None:
        return Decimal(0), Decimal(0)
    session.refresh(balance)
    return balance.quantity, balance.value


def test_a_draft_moves_no_stock_until_it_is_completed(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)

    draft = new_receipt(
        owner_client,
        supplier['id'],
        [line(sku.id, 10, 5000)],
        complete=False,
        supplier_invoice='INV-88',
        payment_status='owed',
    )

    assert draft['status'] == 'draft'
    assert draft['number'] is None
    assert draft['supplier_name'] == 'CV Sumber Jaya'
    assert draft['location_name'] == 'Toko'
    assert draft['payment_status'] == 'owed'
    assert Decimal(draft['total_cost']) == 50000
    assert stock_of(session, sku.id) == (0, 0)

    completed = owner_client.post(f'{RECEIPTS}{draft["id"]}/complete').json()

    assert completed['status'] == 'completed'
    assert completed['number'].startswith('BM-')
    assert completed['number'].endswith('-0001')
    assert completed['completed_by_name'] == 'Owner'
    assert stock_of(session, sku.id) == (10, 50000)
    movement = session.exec(
        select(StockMovement).where(StockMovement.sku_id == sku.id)
    ).one()
    assert movement.reason == 'goods_receipt'
    assert movement.document_number == completed['number']


def test_receipt_numbers_run_in_order(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)

    numbers = [
        new_receipt(owner_client, supplier['id'], [line(sku.id, 1, 100)])[
            'number'
        ]
        for _ in range(3)
    ]

    assert [number[-4:] for number in numbers] == ['0001', '0002', '0003']


def test_a_draft_can_be_changed_and_discarded(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    other = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    draft = new_receipt(
        owner_client, supplier['id'], [line(sku.id, 10, 5000)], complete=False
    )
    url = f'{RECEIPTS}{draft["id"]}'

    changed = owner_client.put(
        url,
        json={
            'supplier_id': supplier['id'],
            'received_on': '2026-11-14',
            'note': 'Kiriman kedua',
            'lines': [line(other.id, 3, 7000), line(sku.id, 2, 5500)],
        },
    ).json()

    assert changed['received_on'] == '2026-11-14'
    assert changed['note'] == 'Kiriman kedua'
    assert [
        (item['sku_id'], Decimal(item['quantity']))
        for item in changed['lines']
    ] == [(other.id, 3), (sku.id, 2)]
    assert Decimal(changed['total_cost']) == 32000

    assert owner_client.delete(url).status_code == 204
    assert owner_client.get(url).status_code == 404


def test_a_completed_receipt_cannot_be_changed_or_deleted(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [line(sku.id, 10, 5000)]
    )
    url = f'{RECEIPTS}{receipt["id"]}'
    body = {
        'supplier_id': supplier['id'],
        'received_on': '2026-11-15',
        'lines': [line(sku.id, 99, 1)],
    }

    assert owner_client.put(url, json=body).status_code == 409
    assert owner_client.delete(url).status_code == 409
    assert owner_client.post(f'{url}/complete').status_code == 409
    assert stock_of(session, sku.id) == (10, 50000)
    assert owner_client.get(url).json() == receipt


def test_a_line_in_purchase_packs_becomes_stock_units(
    owner_client: TestClient, session: Session
) -> None:
    pulpen = new_sku(
        owner_client,
        session,
        size=None,
        purchase_pack_name='box',
        purchase_pack_size=12,
    )
    supplier = new_supplier(owner_client)

    receipt = new_receipt(
        owner_client,
        supplier['id'],
        [line(pulpen.id, 2, 60000, in_packs=True)],
    )

    item = receipt['lines'][0]
    assert Decimal(item['quantity']) == 24
    assert Decimal(item['unit_cost']) == 5000
    assert Decimal(item['total_cost']) == 120000
    assert item['pack_name'] == 'box'
    assert Decimal(item['pack_quantity']) == 2
    assert Decimal(item['pack_cost']) == 60000
    assert stock_of(session, pulpen.id) == (24, 120000)


def test_pack_cost_that_does_not_divide_evenly_keeps_the_exact_total(
    owner_client: TestClient, session: Session
) -> None:
    pulpen = new_sku(
        owner_client,
        session,
        size=None,
        purchase_pack_name='box',
        purchase_pack_size=12,
    )
    supplier = new_supplier(owner_client)

    new_receipt(
        owner_client,
        supplier['id'],
        [line(pulpen.id, 1, 55000, in_packs=True)],
    )

    assert stock_of(session, pulpen.id) == (12, 55000)


def test_a_sku_without_a_purchase_pack_cannot_be_received_in_packs(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)

    response = owner_client.post(
        RECEIPTS,
        json={
            'supplier_id': supplier['id'],
            'received_on': '2026-11-15',
            'lines': [line(sku.id, 2, 60000, in_packs=True)],
        },
    )

    assert response.status_code == 400
    assert 'tidak punya kemasan beli' in response.json()['detail']


def test_an_empty_draft_cannot_be_completed(
    owner_client: TestClient,
) -> None:
    supplier = new_supplier(owner_client)
    draft = new_receipt(owner_client, supplier['id'], [], complete=False)

    response = owner_client.post(f'{RECEIPTS}{draft["id"]}/complete')

    assert response.status_code == 409


def test_receipt_needs_a_real_active_supplier_and_real_skus(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    body = {'received_on': '2026-11-15', 'lines': [line(sku.id, 1, 100)]}

    unknown_supplier = owner_client.post(
        RECEIPTS, json={**body, 'supplier_id': 9999}
    )
    unknown_sku = owner_client.post(
        RECEIPTS,
        json={
            **body,
            'supplier_id': supplier['id'],
            'lines': [line(9999, 1, 100)],
        },
    )
    owner_client.patch(
        f'/api/v1/suppliers/{supplier["id"]}', json={'is_active': False}
    )
    inactive_supplier = owner_client.post(
        RECEIPTS, json={**body, 'supplier_id': supplier['id']}
    )

    assert unknown_supplier.status_code == 404
    assert unknown_sku.status_code == 404
    assert inactive_supplier.status_code == 409


def test_quantity_must_be_positive_and_cost_not_negative(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    body = {'supplier_id': supplier['id'], 'received_on': '2026-11-15'}

    zero = owner_client.post(
        RECEIPTS, json={**body, 'lines': [line(sku.id, 0, 100)]}
    )
    negative_cost = owner_client.post(
        RECEIPTS, json={**body, 'lines': [line(sku.id, 1, -1)]}
    )
    free_goods = owner_client.post(
        RECEIPTS, json={**body, 'lines': [line(sku.id, 1, 0)]}
    )

    assert zero.status_code == 422
    assert negative_cost.status_code == 422
    assert free_goods.status_code == 201


def test_receipts_are_listed_newest_first_and_filter_by_status(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    completed = new_receipt(
        owner_client, supplier['id'], [line(sku.id, 10, 5000)]
    )
    draft = new_receipt(
        owner_client,
        supplier['id'],
        [line(sku.id, 1, 100), line(sku.id, 2, 200)],
        complete=False,
    )

    everything = owner_client.get(RECEIPTS).json()
    drafts = owner_client.get(RECEIPTS, params={'status': 'draft'}).json()

    assert everything['total'] == 2
    assert [item['id'] for item in everything['items']] == [
        draft['id'],
        completed['id'],
    ]
    assert everything['items'][0]['line_count'] == 2
    assert everything['items'][1]['number'] == completed['number']
    assert everything['items'][1]['supplier_name'] == 'CV Sumber Jaya'
    assert [item['id'] for item in drafts['items']] == [draft['id']]


def test_receipts_are_written_to_the_activity_log(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    supplier = new_supplier(owner_client)
    receipt = new_receipt(
        owner_client, supplier['id'], [line(sku.id, 10, 5000)]
    )

    entries = session.exec(
        select(ActivityLog)
        .where(ActivityLog.entity_type == 'goods_receipt')
        .order_by(col(ActivityLog.id))
    ).all()

    assert [entry.action for entry in entries] == [
        'goods_receipt.create',
        'goods_receipt.complete',
    ]
    assert entries[1].summary == (
        f'Menyelesaikan barang masuk {receipt["number"]} dari '
        'CV Sumber Jaya: 1 baris, Rp 50.000.'
    )


def test_a_cashier_cannot_receive_goods(
    client: TestClient, session: Session
) -> None:
    make_user(session, 'kasir', Role.cashier)
    sign_in(client, 'kasir')

    assert client.get(RECEIPTS).status_code == 403
    assert client.post(RECEIPTS, json={}).status_code == 403


def test_two_receipts_completed_at_once_leave_the_right_balance(
    engine: Engine,
) -> None:
    """Real commits on separate connections, cleaned up afterwards."""
    try:
        with Session(engine) as session:
            owner = users.create_user(
                session,
                UserCreate(
                    username='owner',
                    full_name='Owner',
                    role=Role.owner,
                    password='rahasia-123',
                ),
                actor=None,
            )
            category = catalogue.create_category(
                session, CategoryCreate(name='Seragam'), actor=owner
            )
            sub_category = catalogue.create_sub_category(
                session, category, 'Kemeja', actor=owner
            )
            assert sub_category.id is not None
            product = catalogue.create_product(
                session,
                ProductSave(
                    name='Kemeja',
                    sub_category_id=sub_category.id,
                    skus=[SkuSave(selling_price=85000)],
                ),
                actor=owner,
            )
            sku_id = product.skus[0].id
            supplier = suppliers.create_supplier(
                session, SupplierCreate(name='CV Sumber'), actor=owner
            )
            assert sku_id is not None
            assert supplier.id is not None
            receipt_ids = [
                goods_receipts.create_draft(
                    session,
                    GoodsReceiptSave(
                        supplier_id=supplier.id,
                        received_on=date(2026, 11, 15),
                        lines=[
                            GoodsReceiptLineSave(
                                sku_id=sku_id,
                                quantity=Decimal(quantity),
                                unit_cost=Decimal(5000),
                            )
                        ],
                    ),
                    actor=owner,
                ).id
                for quantity in (10, 15)
            ]
            owner_id = owner.id

        start = threading.Barrier(2)
        errors: list[BaseException] = []

        def complete(receipt_id: int | None) -> None:
            try:
                with Session(engine) as session:
                    receipt = session.get(GoodsReceipt, receipt_id)
                    actor = session.get(User, owner_id)
                    assert receipt is not None
                    assert actor is not None
                    start.wait(timeout=5)
                    goods_receipts.complete(session, receipt, actor=actor)
            except BaseException as error:
                errors.append(error)

        threads = [
            threading.Thread(target=complete, args=(receipt_id,))
            for receipt_id in receipt_ids
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)

        assert errors == []
        with Session(engine) as session:
            balance = session.exec(select(StockBalance)).one()
            numbers = session.exec(select(GoodsReceipt.number)).all()
            movements = session.exec(
                select(StockMovement).order_by(col(StockMovement.id))
            ).all()
        assert (balance.quantity, balance.value) == (25, 125000)
        assert sorted(number[-4:] for number in numbers if number) == [
            '0001',
            '0002',
        ]
        assert [m.quantity_after for m in movements][-1] == 25
        assert sum(m.quantity for m in movements) == 25
    finally:
        wipe(engine)
