"""Budget model for storing an allocation of expenses per month."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import orm
from typing_extensions import override

from nummus.models.base import Base, Decimal6, ORMInt, ORMReal

if TYPE_CHECKING:
    from decimal import Decimal


class Budget(Base):
    """Budget model for storing an allocation of expenses per month.

    Attributes:
        uri: Budget unique identifier
        date_ord: Date ordinal on which Budget is effective
        amount: Target limit of expense per month, zero or negative
    """

    __table_id__ = 0x50000000

    date_ord: ORMInt = orm.mapped_column(unique=True)
    amount: ORMReal = orm.mapped_column(
        Decimal6,
        sqlalchemy.CheckConstraint(
            "amount <= 0",
            "budget.amount must be zero or negative",
        ),
    )

    @orm.validates("amount")
    @override
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return super().validate_decimals(key, field)
