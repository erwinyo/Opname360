from collections.abc import Sequence

from sqlmodel import Session, select

from opname360.models import Item, ItemCreate, ItemUpdate


def list_items(session: Session, *, offset: int, limit: int) -> Sequence[Item]:
    return session.exec(select(Item).offset(offset).limit(limit)).all()


def get_item(session: Session, item_id: int) -> Item | None:
    return session.get(Item, item_id)


def create_item(session: Session, item_in: ItemCreate) -> Item:
    item = Item.model_validate(item_in)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def update_item(session: Session, item: Item, item_in: ItemUpdate) -> Item:
    item.sqlmodel_update(item_in.model_dump(exclude_unset=True))
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


def delete_item(session: Session, item: Item) -> None:
    session.delete(item)
    session.commit()
