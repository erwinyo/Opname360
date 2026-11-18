"""Every change to stock goes through here.

`receive` and `issue` lock the SKU's balance, apply the costing rules in
docs/plan.md and write the Stock Movement. Callers own the transaction.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from opname360.models import (
    Category,
    CostLayer,
    CostingMethod,
    MovementReason,
    Product,
    Sku,
    StockBalance,
    StockMovement,
    SubCategory,
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
    batch_id: int | None = None,
) -> StockMovement:
    """Goods in: `quantity` Stock Units that cost `value` altogether."""
    assert quantity > 0
    assert value >= 0
    assert sku.id is not None
    balance = lock_balance(session, sku.id, location_id)
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
        batch_id=batch_id,
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
    unit_cost: Decimal | None = None,
    layer_of: int | None = None,
    batch_id: int | None = None,
) -> StockMovement:
    """Goods out, costed by the SKU's Costing Method.

    The cost is `-movement.value`. Stock never blocks it: what the system
    doesn't hold goes out at the SKU's latest unit cost (costing rule 6).

    A Reversal passes the cost the goods came in at as `unit_cost`, and under
    FIFO the movement that brought them in as `layer_of`, so taking them back
    restores the stock as it was (costing rule 7).
    """
    assert quantity > 0
    assert sku.id is not None
    balance = lock_balance(session, sku.id, location_id)

    available = max(balance.quantity, ZERO)
    from_stock = min(quantity, available)
    oversold = quantity - from_stock

    if from_stock == available:
        # Costing rule 8: the last unit takes the rounding remainder along.
        cost = max(balance.value, ZERO) if available > 0 else ZERO
        _consume_layers(session, sku.id, location_id, None)
    elif _method(sku) == CostingMethod.fifo:
        cost = _consume_layers(
            session, sku.id, location_id, from_stock, first=layer_of
        )
    elif unit_cost is not None:
        # Never take out more value than the stock holds.
        cost = min(money(from_stock * unit_cost), max(balance.value, ZERO))
    else:
        cost = money(from_stock * balance.value / balance.quantity)
    oversold_cost = (
        unit_cost if unit_cost is not None else sku.latest_unit_cost
    )
    cost += money(oversold * (oversold_cost or ZERO))

    return _record(
        session,
        balance,
        reason=reason,
        quantity=-quantity,
        unit_cost=money(cost / quantity),
        value=-cost,
        source=source,
        actor=actor,
        batch_id=batch_id,
    )


def reverse(
    session: Session,
    *,
    document_type: str,
    document_id: int,
    number: str,
    actor: User,
) -> None:
    """Write the opposite of every Stock Movement a document made.

    The new movements point at the same document and carry the Reversal's
    `number`. Goods already gone leave the SKU in Negative Stock.
    """
    originals = session.exec(
        select(StockMovement)
        .where(
            StockMovement.document_type == document_type,
            StockMovement.document_id == document_id,
            StockMovement.reason != MovementReason.reversal,
        )
        # SKU order avoids deadlocks; within a SKU, the original order.
        .order_by(col(StockMovement.sku_id), col(StockMovement.id))
    ).all()
    source = Source(document_type, document_id, number)
    for original in originals:
        sku = session.get(Sku, original.sku_id)
        assert sku is not None
        if original.quantity > 0:
            issue(
                session,
                sku=sku,
                location_id=original.location_id,
                quantity=original.quantity,
                reason=MovementReason.reversal,
                source=source,
                actor=actor,
                unit_cost=original.unit_cost,
                layer_of=original.id,
                batch_id=original.batch_id,
            )
        elif original.quantity < 0:
            receive(
                session,
                sku=sku,
                location_id=original.location_id,
                quantity=-original.quantity,
                value=-original.value,
                reason=MovementReason.reversal,
                source=source,
                actor=actor,
                sets_latest_cost=False,
                batch_id=original.batch_id,
            )
        else:
            balance = lock_balance(
                session, original.sku_id, original.location_id
            )
            _record(
                session,
                balance,
                reason=MovementReason.reversal,
                quantity=ZERO,
                unit_cost=ZERO,
                value=-original.value,
                source=source,
                actor=actor,
            )
        session.flush()


def found(
    session: Session,
    *,
    sku: Sku,
    location_id: int,
    quantity: Decimal,
    reason: MovementReason,
    source: Source,
    actor: User | None,
    unit_cost: Decimal | None = None,
    batch_id: int | None = None,
) -> StockMovement:
    """A Surplus found in an opname, valued by costing rule 5.

    `unit_cost` was entered by hand and is used only when the SKU has never
    had a cost; it then becomes the SKU's latest unit cost.
    """
    assert sku.id is not None
    balance = lock_balance(session, sku.id, location_id)
    cost = found_unit_cost(sku, balance)
    if cost is None:
        assert unit_cost is not None, 'the caller checks a cost is known'
        cost = unit_cost
    return receive(
        session,
        sku=sku,
        location_id=location_id,
        quantity=quantity,
        value=money(quantity * cost),
        reason=reason,
        source=source,
        actor=actor,
        sets_latest_cost=sku.latest_unit_cost is None,
        batch_id=batch_id,
    )


def found_unit_cost(sku: Sku, balance: StockBalance | None) -> Decimal | None:
    """Costing rule 5: what one unit found in an opname is worth.

    The current average cost under Moving Average, the latest unit cost under
    FIFO (or when there is nothing to average). None if the SKU has never had
    a cost.
    """
    if (
        _method(sku) == CostingMethod.moving_average
        and balance is not None
        and balance.quantity > 0
    ):
        return money(balance.value / balance.quantity)
    return sku.latest_unit_cost


def switch_method(
    session: Session, category: Category, method: CostingMethod
) -> Decimal:
    """Change a Category's Costing Method from now on (ADR 0002).

    FIFO -> Moving Average drops the Cost Layers, leaving their average;
    Moving Average -> FIFO starts each SKU from one layer at its average
    cost. Stock Value doesn't change; it is returned for the log.
    """
    sku_ids = (
        select(Sku.id)
        .join(Product)
        .join(SubCategory)
        .where(SubCategory.category_id == category.id)
    )
    # Every balance of the Category, so no sale moves stock mid-switch.
    balances = session.exec(
        select(StockBalance)
        .where(col(StockBalance.sku_id).in_(sku_ids))
        .order_by(col(StockBalance.sku_id), col(StockBalance.location_id))
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    for layer in session.exec(
        select(CostLayer).where(col(CostLayer.sku_id).in_(sku_ids))
    ).all():
        session.delete(layer)
    if method == CostingMethod.fifo:
        for balance in balances:
            if balance.quantity > 0:
                session.add(
                    CostLayer(
                        sku_id=balance.sku_id,
                        location_id=balance.location_id,
                        unit_cost=money(balance.value / balance.quantity),
                        quantity_remaining=balance.quantity,
                    )
                )
    category.costing_method = method
    session.add(category)
    return sum((balance.value for balance in balances), ZERO)


def _method(sku: Sku) -> CostingMethod:
    return sku.product.sub_category.category.costing_method


def lock_balance(
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
    batch_id: int | None = None,
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
        batch_id=batch_id,
        created_by=actor.id if actor else None,
    )
    session.add(movement)
    return movement


def _consume_layers(
    session: Session,
    sku_id: int,
    location_id: int,
    quantity: Decimal | None,
    *,
    first: int | None = None,
) -> Decimal:
    """Take `quantity` from the oldest Cost Layers (all of them for None).

    The layer made by movement `first`, if still there, goes before the rest.
    Returns what the taken units cost.
    """
    layers = sorted(
        session.exec(
            select(CostLayer)
            .where(
                CostLayer.sku_id == sku_id,
                CostLayer.location_id == location_id,
            )
            .order_by(col(CostLayer.received_at), col(CostLayer.id))
        ).all(),
        key=lambda layer: layer.movement_id != first,
    )
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
