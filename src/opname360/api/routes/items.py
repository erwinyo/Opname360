from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from opname360.api.deps import SessionDep
from opname360.models import Item, ItemCreate, ItemPublic, ItemUpdate
from opname360.services import items as items_service

router = APIRouter(prefix="/items", tags=["items"])


def get_item_or_404(session: SessionDep, item_id: Annotated[int, Path(ge=1)]) -> Item:
    item = items_service.get_item(session, item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
        )
    return item


ItemDep = Annotated[Item, Depends(get_item_or_404)]


@router.get("/", response_model=list[ItemPublic])
def read_items(
    session: SessionDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
):
    return items_service.list_items(session, offset=offset, limit=limit)


@router.post("/", response_model=ItemPublic, status_code=status.HTTP_201_CREATED)
def create_item(session: SessionDep, item_in: ItemCreate):
    return items_service.create_item(session, item_in)


@router.get("/{item_id}", response_model=ItemPublic)
def read_item(item: ItemDep):
    return item


@router.patch("/{item_id}", response_model=ItemPublic)
def update_item(session: SessionDep, item: ItemDep, item_in: ItemUpdate):
    return items_service.update_item(session, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(session: SessionDep, item: ItemDep) -> None:
    items_service.delete_item(session, item)
