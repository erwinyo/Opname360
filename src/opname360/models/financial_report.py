"""Laba Rugi and Neraca (slice 5): worked out from the journal entries
when they run. Nothing here is a table."""

from datetime import date
from decimal import Decimal
from typing import Self

from pydantic import model_validator
from sqlmodel import SQLModel


class StatementLine(SQLModel):
    # None for a figure worked out rather than an account's balance.
    account_id: int | None
    code: str | None
    name: str
    amount: Decimal


class StatementPeriod(SQLModel):
    start: date
    end: date

    @model_validator(mode='after')
    def a_real_period(self) -> Self:
        if self.end < self.start:
            raise ValueError('Tanggal akhir sebelum tanggal awal.')
        return self


class ProfitAndLoss(SQLModel):
    """Rule 14. Sales lines carry their sign: discounts and returns are
    below zero."""

    start: date
    end: date
    sales: list[StatementLine]
    net_sales: Decimal
    cogs: list[StatementLine]
    total_cogs: Decimal
    gross_profit: Decimal
    expenses: list[StatementLine]
    total_expenses: Decimal
    other_income: list[StatementLine]
    total_other_income: Decimal
    net_profit: Decimal


class BalanceSheet(SQLModel):
    """Rule 13, in T layout: assets on the left, the rest on the right."""

    on: date
    assets: list[StatementLine]
    total_assets: Decimal
    liabilities: list[StatementLine]
    total_liabilities: Decimal
    equity: list[StatementLine]
    total_equity: Decimal
    total_liabilities_and_equity: Decimal


class LockDate(SQLModel):
    # The books are closed up to and including this day; None: all open.
    lock_date: date | None
