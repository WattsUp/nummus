"""Budget model for storing an allocation of expenses per month."""

from __future__ import annotations

import datetime
import math
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, func, orm, UniqueConstraint

from nummus import utils
from nummus.models.account import Account
from nummus.models.base import (
    Base,
    BaseEnum,
    Decimal6,
    ORMInt,
    ORMIntOpt,
    ORMReal,
    ORMStr,
    SQLEnum,
    string_column_args,
    YIELD_PER,
)
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)


class BudgetGroup(Base):
    """Budget group model for storing a grouping of categories.

    Attributes:
        name: Group name
        position: Group position
    """

    __table_id__ = 0x40000000

    name: ORMStr = orm.mapped_column(unique=True)
    position: ORMInt = orm.mapped_column(unique=True)

    __table_args__ = (*string_column_args("name"),)

    @orm.validates("name")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints."""
        return self.clean_strings(key, field, short_check=key != "ticker")


class BudgetAssignment(Base):
    """Budget assignment model for storing an contribution to a budget category.

    Attributes:
        month_ord: Date ordinal on which BudgetAssignment occurred (1st of month)
        amount: Amount contributed to budget category
        category_id: Budget category to contribute to
    """

    __table_id__ = None

    month_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    __table_args__ = (UniqueConstraint("month_ord", "category_id"),)

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimal fields satisfy constraints."""
        return self.clean_decimals(key, field)

    @classmethod
    def get_monthly_available(
        cls,
        s: orm.Session,
        month: datetime.date,
    ) -> tuple[dict[int, tuple[Decimal, Decimal, Decimal, Decimal]], Decimal, Decimal]:
        """Get available budget for a month.

        Args:
            s: SQL session to use
            month: Month to compute budget during

        Returns:
            (
                dict{TransactionCategory: (assigned, activity, available, leftover)},
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
                func.sum(TransactionSplit.amount),
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
                func.sum(TransactionSplit.amount),
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
            .with_entities(func.sum(BudgetAssignment.amount))
            .where(BudgetAssignment.month_ord > month_ord)
        )
        future_assigned = query.scalar() or Decimal(0)

        # Current month's activity
        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.category_id,
                func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.month_ord == month_ord,
            )
            .group_by(TransactionSplit.category_id)
        )
        categories_activity: dict[int, Decimal] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        categories: dict[int, tuple[Decimal, Decimal, Decimal, Decimal]] = {}
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
            categories[t_cat_id] = (assigned, activity, available, leftover)

        assignable = ending_balance - total_available
        if assignable < 0:
            future_assigned = Decimal(0)
        else:
            future_assigned = min(future_assigned, assignable)
            assignable -= future_assigned

        return categories, assignable, future_assigned


class TargetType(BaseEnum):
    """Type of budget target."""

    ACCUMULATE = 1
    REFILL = 2
    BALANCE = 3


class TargetPeriod(BaseEnum):
    """Type of budget due date."""

    WEEK = 1
    MONTH = 2
    YEAR = 3
    ONCE = 4


class Target(Base):
    """Budget target model for storing a desired budget amount.

    Attributes:
        category_id: Budget category to target
        amount: Amount to target
        type_: Type of budget target
        period: Type of budget due date
        due_date_ord: First date ordinal on which target is due
        repeat_every: Repeat target every n period
    """

    __table_id__ = 0x70000000

    category_id: ORMInt = orm.mapped_column(
        ForeignKey("transaction_category.id_"),
        unique=True,
    )
    amount: ORMReal = orm.mapped_column(
        Decimal6,
        CheckConstraint("amount > 0", "target.amount must be positive"),
    )
    type_: orm.Mapped[TargetType] = orm.mapped_column(SQLEnum(TargetType))
    period: orm.Mapped[TargetPeriod] = orm.mapped_column(SQLEnum(TargetPeriod))
    due_date_ord: ORMIntOpt
    repeat_every: ORMInt

    __table_args__ = (
        CheckConstraint(
            f"(period == {TargetPeriod.ONCE.value}) == (repeat_every == 0)",
            "ONCE are the only that cannot repeat",
        ),
        CheckConstraint(
            f"(period == {TargetPeriod.ONCE.value}) == "
            f"(type_ == {TargetType.BALANCE.value})",
            "ONCE targets must be BALANCE",
        ),
        CheckConstraint(
            f"type_ == {TargetType.BALANCE.value} or due_date_ord IS NOT null",
            "Only BALANCE targets cannot have a due date",
        ),
        CheckConstraint(
            f"period != {TargetPeriod.WEEK.value} or repeat_every == 1",
            "WEEK targets must repeat every week",
        ),
    )

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimal fields satisfy constraints."""
        return self.clean_decimals(key, field)

    def get_expected_assigned(
        self,
        month: datetime.date,
        leftover: Decimal,
    ) -> tuple[Decimal, datetime.date | None, int, bool]:
        """Get expected assigned amount.

        Args:
            month: Month to check progress during
            leftover: Category leftover balance from previous month

        Returns:
            (
                expected assigned amount,
                next due date,
                number of target amounts this month,
                last repeat was last month,
            )
        """
        if self.due_date_ord is None:
            # No due date, easy to figure out progress
            return self.amount - leftover, None, 1, False

        due_date = datetime.date.fromordinal(self.due_date_ord)
        if self.period == TargetPeriod.WEEK:
            # Need the number of weekdays that fall in this month
            n_weekdays = utils.weekdays_in_month(due_date.weekday(), month)
            amount = n_weekdays * self.amount
            return (
                (amount if self.type_ == TargetType.ACCUMULATE else amount - leftover),
                None,
                n_weekdays,
                True,
            )

        # Get next due date
        if self.period == TargetPeriod.ONCE:
            if month >= due_date:
                # Non-repeating target is in the past
                # Should be fully funded by now
                return self.amount - leftover, None, 1, False
            n_months = utils.date_months_between(month, due_date)
            return (self.amount - leftover) / (n_months + 1), due_date, 1, False

        # Move due_date into month
        n = utils.date_months_between(due_date, month)
        n_months_every = (
            self.repeat_every
            if self.period == TargetPeriod.MONTH
            else self.repeat_every * 12
        )
        n = math.ceil(n / n_months_every) * n_months_every
        due_date = utils.date_add_months(due_date, n)
        last_due_date = utils.date_add_months(due_date, -n_months_every)
        last_repeat_last_month = utils.date_months_between(last_due_date, month) == 1

        # If ACCUMULATE and last repeat ended last month, ignore balance
        if self.type_ == TargetType.ACCUMULATE and last_repeat_last_month:
            deficient = self.amount
        else:
            deficient = self.amount - leftover
        n_months = utils.date_months_between(month, due_date)
        return deficient / (n_months + 1), due_date, 1, last_repeat_last_month
