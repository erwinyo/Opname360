from sqlmodel import Field, SQLModel


class PaymentMethodBase(SQLModel):
    name: str = Field(min_length=1, max_length=50, unique=True)
    is_active: bool = True


class PaymentMethod(PaymentMethodBase, table=True):
    __tablename__ = 'payment_method'

    id: int | None = Field(default=None, primary_key=True)
    # Cash goes into the Shift's drawer; change and refunds come out of it.
    # Fixed when created, so past Shifts keep adding up.
    is_cash: bool = False


class PaymentMethodCreate(PaymentMethodBase):
    is_cash: bool = False


class PaymentMethodUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    is_active: bool | None = None


class PaymentMethodPublic(PaymentMethodBase):
    id: int
    is_cash: bool
