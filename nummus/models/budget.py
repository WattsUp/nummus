"""Budget model for storing an allocation of expenses per month."""

from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy
from sqlalchemy import ForeignKey, orm
from typing_extensions import override

from nummus import utils
from nummus.models.account import Account
from nummus.models.base import Base, Decimal6, ORMInt, ORMReal, YIELD_PER
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)


class BudgetAssignment(Base):
    """Budget assignment model for storing an contribution to a budget category.

    Attributes:
        month_ord: Date ordinal on which BudgetAssignment occurred (1st of month)
        amount: Amount contributed to budget category
        category_id: Budget category to contribute to
    """

    # No __table_id__ because this is not user accessible

    month_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    __table_args__ = (sqlalchemy.UniqueConstraint("month_ord", "category_id"),)

    @orm.validates("amount")
    @override
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return super().validate_decimals(key, field)

    @classmethod
    def get_monthly_available(
        cls,
        s: orm.Session,
        month: datetime.date,
    ) -> tuple[dict[int, tuple[Decimal, Decimal, Decimal]], Decimal, Decimal]:
        """Get available budget for a month.

        Args:
            s: SQL session to use
            month: Month to compute budget during

        Returns:
            (
                dict{TransactionCategory: (assigned, activity, available)},
                assignable,
                future_assigned,
            )
        """
        month_ord = month.toordinal()
        query = s.query(Account).where(Account.budgeted)

        # Include account if not closed
        # Include account if most recent transaction is in period
        def include_account(acct: Account) -> bool:
            if not acct.closed:
                return True
            updated_on_ord = acct.updated_on_ord
            return updated_on_ord is not None and updated_on_ord >= month_ord

        accounts = {
            acct.id_: acct.name for acct in query.all() if include_account(acct)
        }

        # Starting balance
        query = (
            s.query(TransactionSplit)
            .with_entities(
                sqlalchemy.func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.date_ord < month_ord,
            )
        )
        starting_balance = query.scalar() or Decimal(0)
        ending_balance = starting_balance
        total_available = Decimal(0)

        # Check all categories not INCOME
        budget_categories = {
            t_cat_id
            for t_cat_id, in s.query(TransactionCategory.id_)
            .where(TransactionCategory.group != TransactionCategoryGroup.INCOME)
            .all()
        }

        # Current month's assignment
        query = (
            s.query(BudgetAssignment)
            .with_entities(BudgetAssignment.category_id, BudgetAssignment.amount)
            .where(BudgetAssignment.month_ord == month_ord)
        )
        categories_assigned: dict[int, Decimal] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        # Prior months' assignment
        min_month_ord = month_ord
        prior_assigned: dict[int, dict[int, Decimal]] = {
            t_cat_id: {} for t_cat_id in budget_categories
        }
        query = (
            s.query(BudgetAssignment)
            .with_entities(
                BudgetAssignment.category_id,
                BudgetAssignment.amount,
                BudgetAssignment.month_ord,
            )
            .where(BudgetAssignment.month_ord < month_ord)
            .order_by(BudgetAssignment.month_ord)
        )
        for cat_id, amount, m_ord in query.yield_per(YIELD_PER):
            prior_assigned[cat_id][m_ord] = amount
            min_month_ord = min(min_month_ord, m_ord)

        # Prior months' activity
        prior_activity: dict[int, dict[int, Decimal]] = {
            t_cat_id: {} for t_cat_id in budget_categories
        }
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.category_id,
                sqlalchemy.func.sum(TransactionSplit.amount),
                TransactionSplit.month_ord,
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.month_ord < month_ord,
                TransactionSplit.month_ord >= min_month_ord,
                TransactionSplit.category_id.in_(budget_categories),
            )
            .group_by(
                TransactionSplit.category_id,
                TransactionSplit.month_ord,
            )
        )
        for cat_id, amount, m_ord in query.yield_per(YIELD_PER):
            prior_activity[cat_id][m_ord] = amount

        # Carry over leftover to next months to get current month's leftover amounts
        categories_leftover: dict[int, Decimal] = {
            t_cat_id: Decimal(0) for t_cat_id in budget_categories
        }
        date = datetime.date.fromordinal(min_month_ord)
        while date < month:
            date_ord = date.toordinal()
            for t_cat_id in budget_categories:
                assigned = categories_leftover[t_cat_id] + prior_assigned[t_cat_id].get(
                    date_ord,
                    Decimal(0),
                )
                activity = prior_activity[t_cat_id].get(date_ord, Decimal(0))
                leftover = assigned + activity
                categories_leftover[t_cat_id] = max(Decimal(0), leftover)
            date = utils.date_add_months(date, 1)

        # Future months' assignment
        query = (
            s.query(BudgetAssignment)
            .with_entities(sqlalchemy.func.sum(BudgetAssignment.amount))
            .where(BudgetAssignment.month_ord > month_ord)
        )
        future_assigned = query.scalar() or Decimal(0)

        # Current month's activity
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.category_id,
                sqlalchemy.func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.month_ord == month_ord,
            )
            .group_by(TransactionSplit.category_id)
        )
        categories_activity: dict[int, Decimal] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        categories: dict[int, tuple[Decimal, Decimal, Decimal]] = {}
        query = s.query(TransactionCategory).with_entities(
            TransactionCategory.id_,
            TransactionCategory.group,
        )
        for t_cat_id, group in query.yield_per(YIELD_PER):
            activity = categories_activity.get(t_cat_id, Decimal(0))
            assigned = categories_assigned.get(t_cat_id, Decimal(0))
            leftover = categories_leftover.get(t_cat_id, Decimal(0))
            available = (
                Decimal(0)
                if group == TransactionCategoryGroup.INCOME
                else assigned + activity + leftover
            )

            ending_balance += activity
            total_available += available
            categories[t_cat_id] = (assigned, activity, available)

        assignable = ending_balance - total_available
        if assignable < 0:
            future_assigned = Decimal(0)
        else:
            future_assigned = min(future_assigned, assignable)
            assignable -= future_assigned

        return categories, assignable, future_assigned


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
