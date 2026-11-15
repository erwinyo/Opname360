from decimal import Decimal

import pytest

from fastapi.testclient import TestClient
from sqlmodel import Session, col, select

from .conftest import new_sku

from opname360.models import (
    CostLayer,
    MovementReason,
    Sku,
    StockBalance,
    StockMovement,
)
from opname360.services import costing, stock


SOURCE = costing.Source('test', 1, 'TEST-1')
BOTH_METHODS = pytest.mark.parametrize('method', ['moving_average', 'fifo'])


def receive(
    session: Session, sku: Sku, quantity: int, unit_cost: int
) -> StockMovement:
    return costing.receive(
        session,
        sku=sku,
        location_id=stock.resolve_location(session, None),
        quantity=Decimal(quantity),
        value=Decimal(quantity * unit_cost),
        reason=MovementReason.goods_receipt,
        source=SOURCE,
        actor=None,
    )


def issue(session: Session, sku: Sku, quantity: int) -> Decimal:
    """Take `quantity` out and return what it cost."""
    movement = costing.issue(
        session,
        sku=sku,
        location_id=stock.resolve_location(session, None),
        quantity=Decimal(quantity),
        reason=MovementReason.supplier_return,
        source=SOURCE,
        actor=None,
    )
    session.flush()
    return -movement.value


def on_hand(session: Session, sku: Sku) -> tuple[Decimal, Decimal]:
    session.flush()
    balance = session.exec(
        select(StockBalance).where(StockBalance.sku_id == sku.id)
    ).one()
    session.refresh(balance)
    return balance.quantity, balance.value


def layers(session: Session, sku: Sku) -> list[tuple[Decimal, Decimal]]:
    session.flush()
    return [
        (layer.quantity_remaining, layer.unit_cost)
        for layer in session.exec(
            select(CostLayer)
            .where(CostLayer.sku_id == sku.id)
            .order_by(col(CostLayer.id))
        ).all()
    ]


def adjustments(session: Session, sku: Sku) -> list[Decimal]:
    session.flush()
    return [
        movement.value
        for movement in session.exec(
            select(StockMovement).where(
                StockMovement.sku_id == sku.id,
                StockMovement.reason == MovementReason.cost_adjustment,
            )
        ).all()
    ]


def test_moving_average_blends_every_delivery(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'moving_average')

    receive(session, sku, 10, 5000)
    receive(session, sku, 10, 6000)

    assert on_hand(session, sku) == (20, 110000)
    assert layers(session, sku) == []
    assert issue(session, sku, 5) == 27500  # 5 at the 5.500 average
    assert on_hand(session, sku) == (15, 82500)


def test_fifo_takes_from_the_oldest_delivery_first(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session, 'fifo')

    receive(session, sku, 10, 5000)
    receive(session, sku, 10, 6000)

    assert layers(session, sku) == [(10, 5000), (10, 6000)]
    assert issue(session, sku, 12) == 62000  # 10 at 5.000, then 2 at 6.000
    assert layers(session, sku) == [(8, 6000)]
    assert on_hand(session, sku) == (8, 48000)


@BOTH_METHODS
def test_the_last_unit_takes_the_rounding_remainder(
    owner_client: TestClient, session: Session, method: str
) -> None:
    sku = new_sku(owner_client, session, method)
    costing.receive(
        session,
        sku=sku,
        location_id=stock.resolve_location(session, None),
        quantity=Decimal(3),
        value=Decimal(10000),  # 3.333,3333 each
        reason=MovementReason.goods_receipt,
        source=SOURCE,
        actor=None,
    )

    costs = [issue(session, sku, 1) for _ in range(3)]

    assert sum(costs) == 10000
    assert on_hand(session, sku) == (0, 0)
    assert layers(session, sku) == []


@BOTH_METHODS
def test_selling_more_than_is_held_goes_out_at_the_latest_cost(
    owner_client: TestClient, session: Session, method: str
) -> None:
    sku = new_sku(owner_client, session, method)
    receive(session, sku, 3, 5000)

    cost = issue(session, sku, 5)

    assert cost == 25000  # 3 in stock and 2 oversold, all at 5.000
    assert on_hand(session, sku) == (-2, -10000)


@BOTH_METHODS
def test_a_delivery_fills_negative_stock_first(
    owner_client: TestClient, session: Session, method: str
) -> None:
    sku = new_sku(owner_client, session, method)
    receive(session, sku, 3, 5000)
    issue(session, sku, 5)

    receive(session, sku, 10, 6000)

    # 8 of the 10 are left, at what they cost. The 2 already sold were costed
    # at 5.000 but cost 6.000: Rp 2.000 leaves Stock Value as an adjustment.
    assert on_hand(session, sku) == (8, 48000)
    assert adjustments(session, sku) == [-2000]
    assert layers(session, sku) == ([(8, 6000)] if method == 'fifo' else [])


@BOTH_METHODS
def test_a_delivery_smaller_than_the_gap_leaves_stock_negative(
    owner_client: TestClient, session: Session, method: str
) -> None:
    sku = new_sku(owner_client, session, method)
    receive(session, sku, 1, 5000)
    issue(session, sku, 6)
    assert on_hand(session, sku) == (-5, -25000)

    receive(session, sku, 2, 6000)

    assert on_hand(session, sku) == (-3, -15000)
    assert adjustments(session, sku) == [-2000]
    assert layers(session, sku) == []


def test_a_sku_that_never_had_a_cost_goes_out_at_zero_until_goods_arrive(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)

    assert issue(session, sku, 2) == 0
    assert on_hand(session, sku) == (-2, 0)

    receive(session, sku, 5, 4000)

    assert on_hand(session, sku) == (3, 12000)
    assert adjustments(session, sku) == [-8000]


def test_a_delivery_sets_the_latest_unit_cost(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    assert sku.latest_unit_cost is None

    receive(session, sku, 10, 5000)
    receive(session, sku, 4, 6500)

    assert sku.latest_unit_cost == 6500


def test_each_movement_records_the_balance_after_it(
    owner_client: TestClient, session: Session
) -> None:
    sku = new_sku(owner_client, session)
    receive(session, sku, 10, 5000)
    issue(session, sku, 4)
    receive(session, sku, 6, 6000)

    session.flush()
    movements = session.exec(
        select(StockMovement)
        .where(StockMovement.sku_id == sku.id)
        .order_by(col(StockMovement.id))
    ).all()

    assert [
        (m.quantity, m.value, m.quantity_after, m.value_after)
        for m in movements
    ] == [
        (10, 50000, 10, 50000),
        (-4, -20000, 6, 30000),
        (6, 36000, 12, 66000),
    ]
