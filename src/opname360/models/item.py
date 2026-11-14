from sqlmodel import Field, SQLModel


class ItemBase(SQLModel):
    name: str = Field(min_length=1, max_length=255, index=True)
    description: str | None = Field(default=None, max_length=1000)
    quantity: int = Field(default=0, ge=0)


class Item(ItemBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class ItemCreate(ItemBase):
    pass


class ItemUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    quantity: int | None = Field(default=None, ge=0)


class ItemPublic(ItemBase):
    id: int
