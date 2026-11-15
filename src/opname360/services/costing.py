"""Every change to stock goes through here.

`receive` and `issue` lock the SKU's balance, apply the costing rules in
docs/plan.md and write the Stock Movement. Callers own the transaction.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from opname360.models import (
    CostLayer,
    CostingMethod,
    MovementReason,
    Sku,
    StockBalance,
    StockMovement,
    User,
)


ZERO = Decimal(0)
FOUR_PLACES = Decimal('0.0001')


def money(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Source:
    """The document a movement belongs to."""

    type: str
    id: int
    number: str


def receive(
    session: Session,
    *,
    sku: Sku,
    location_id: int,
    quantity: Decimal,
    value: Decimal,
    reason: MovementReason,
    source: Source,
    actor: User | None,
    sets_latest_cost: bool = True,
) -> StockMovement:
    """Goods in: `quantity` Stock Units that cost `value` altogether."""
    assert quantity > 0
    assert value >= 0
    assert sku.id is not None
    balance = _lock_balance(session, sku.id, location_id)
    unit_cost = money(value / quantity)

    old_quantity, old_value = balance.quantity, balance.value
    new_quantity = old_quantity + quantity
    # Costing rule 6: a delivery first fills Negative Stock.
    if old_quantity >= 0:
        new_value = old_value + value
    elif new_quantity >= 0:
        # Only what is left of this delivery is in stock, at its own cost.
        new_value = money(value * new_quantity / quantity)
    else:
        # Still oversold, at the cost those sales were booked at.
        new_value = money(old_value * new_quantity / old_quantity)

    movement = _record(
        session,
        balance,
        reason=reason,
        quantity=quantity,
        unit_cost=unit_cost,
        value=value,
        source=source,
        actor=actor,
    )
    session.flush()
    assert movement.id is not None

    # The sales that created the gap were costed at the old latest cost; the
    # difference to what the goods really cost leaves Stock Value here and is
    # booked as a COGS adjustment.
    correction = new_value - balance.value
    if correction != 0:
        _record(
            session,
            balance,
            reason=MovementReason.cost_adjustment,
            quantity=ZERO,
            unit_cost=ZERO,
            value=correction,
            source=source,
            actor=actor,
        )

    in_stock = min(quantity, max(new_quantity, ZERO))
    if _method(sku) == CostingMethod.fifo and in_stock > 0:
        session.add(
            CostLayer(
                sku_id=sku.id,
                location_id=location_id,
                movement_id=movement.id,
                unit_cost=unit_cost,
                quantity_remaining=in_stock,
            )
        )
    if sets_latest_cost:
        sku.latest_unit_cost = unit_cost
        session.add(sku)
    return movement


def issue(
    session: Session,
    *,
    sku: Sku,
    location_id: int,
    quantity: Decimal,
    reason: MovementReason,
    source: Source,
    actor: User | None,
) -> StockMovement:
    """Goods out, costed by the SKU's Costing Method.

    The cost is `-movement.value`. Stock never blocks it: what the system
    doesn't hold goes out at the SKU's latest unit cost (costing rule 6).
    """
    assert quantity > 0
    assert sku.id is not None
    balance = _lock_balance(session, sku.id, location_id)

    available = max(balance.quantity, ZERO)
    from_stock = min(quantity, available)
    oversold = quantity - from_stock

    if from_stock == available:
        # Costing rule 8: the last unit takes the rounding remainder along.
        cost = max(balance.value, ZERO) if available > 0 else ZERO
        _consume_layers(session, sku.id, location_id, None)
    elif _method(sku) == CostingMethod.fifo:
        cost = _consume_layers(session, sku.id, location_id, from_stock)
    else:
        cost = money(from_stock * balance.value / balance.quantity)
    cost += money(oversold * (sku.latest_unit_cost or ZERO))

    return _record(
        session,
        balance,
        reason=reason,
        quantity=-quantity,
        unit_cost=money(cost / quantity),
        value=-cost,
        source=source,
        actor=actor,
    )


def _method(sku: Sku) -> CostingMethod:
    return sku.product.sub_category.category.costing_method


def _lock_balance(
    session: Session, sku_id: int, location_id: int
) -> StockBalance:
    """The SKU's balance row, created if missing, locked until commit."""
    session.exec(
        insert(StockBalance)
        .values(sku_id=sku_id, location_id=location_id, quantity=0, value=0)
        .on_conflict_do_nothing()
    )
    return session.exec(
        select(StockBalance)
        .where(
            StockBalance.sku_id == sku_id,
            StockBalance.location_id == location_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    ).one()


def _record(
    session: Session,
    balance: StockBalance,
    *,
    reason: MovementReason,
    quantity: Decimal,
    unit_cost: Decimal,
    value: Decimal,
    source: Source,
    actor: User | None,
) -> StockMovement:
    """Apply a change to the balance and write its Stock Movement."""
    balance.quantity += quantity
    balance.value = money(balance.value + value)
    session.add(balance)
    movement = StockMovement(
        sku_id=balance.sku_id,
        location_id=balance.location_id,
        reason=reason,
        quantity=quantity,
        unit_cost=unit_cost,
        value=money(value),
        quantity_after=balance.quantity,
        value_after=balance.value,
        document_type=source.type,
        document_id=source.id,
        document_number=source.number,
        created_by=actor.id if actor else None,
    )
    session.add(movement)
    return movement


def _consume_layers(
    session: Session, sku_id: int, location_id: int, quantity: Decimal | None
) -> Decimal:
    """Take `quantity` from the oldest Cost Layers (all of them for None).

    Returns what the taken units cost.
    """
    layers = session.exec(
        select(CostLayer)
        .where(
            CostLayer.sku_id == sku_id,
            CostLayer.location_id == location_id,
        )
        .order_by(col(CostLayer.received_at), col(CostLayer.id))
    ).all()
    cost = ZERO
    for layer in layers:
        if quantity is not None and quantity <= 0:
            break
        take = (
            layer.quantity_remaining
            if quantity is None
            else min(layer.quantity_remaining, quantity)
        )
        cost += money(take * layer.unit_cost)
        if quantity is not None:
            quantity -= take
        if take == layer.quantity_remaining:
            session.delete(layer)
        else:
            layer.quantity_remaining -= take
            session.add(layer)
    return cost
