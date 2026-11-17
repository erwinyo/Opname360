from datetime import time
from typing import Self

from pydantic import model_validator
from sqlmodel import Field, SQLModel


class ShopSettingsBase(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    # Printed at the bottom of every Receipt.
    receipt_footer: str | None = Field(default=None, max_length=300)
    # The hours the Owner's dashboard charts.
    opens_at: time
    closes_at: time
    # Days after a sale a Customer Return is still accepted.
    return_window_days: int = Field(ge=0, le=365)

    @model_validator(mode='after')
    def opens_before_closing(self) -> Self:
        if self.opens_at >= self.closes_at:
            raise ValueError('The shop must open before it closes.')
        return self


class ShopSettings(ShopSettingsBase, table=True):
    """One row: the shop as printed on Receipts, and its selling rules."""

    __tablename__ = 'shop_settings'

    id: int = Field(default=1, primary_key=True)


class ShopSettingsSave(ShopSettingsBase):
    pass


class ShopSettingsPublic(ShopSettingsBase):
    pass
