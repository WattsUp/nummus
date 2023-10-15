"""Budget model for storing an allocation of expenses per month."""

from __future__ import annotations

import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base, Decimal6

ORMBudget = orm.Mapped["Budget"]
ORMBudgetOpt = orm.Mapped[t.Optional["Budget"]]


class Budget(Base):
    """Budget model for storing an allocation of expenses per month.

    Attributes:
        uuid: Budget unique identifier
        date: Date on which Budget is effective
        amount: Target limit of expense per month, zero or negative
    """

    date: t.ORMDate = orm.mapped_column(unique=True)
    amount: t.ORMReal = orm.mapped_column(
        Decimal6,
        sqlalchemy.CheckConstraint(
            "amount <= 0",
            "budget.amount must be zero or negative",
        ),
    )
