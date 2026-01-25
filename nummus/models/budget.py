"""Budget model for storing an allocation of expenses per month."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import CheckConstraint, ForeignKey, func, Index, orm, UniqueConstraint

from nummus import sql, utils
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
)
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)


class BudgetAvailableCategory(NamedTuple):
    """Type returned from get_monthly_available."""

    assigned: Decimal
    activity: Decimal
    available: Decimal
    leftover: Decimal


class BudgetAvailable(NamedTuple):
    """Type returned from get_monthly_available."""

    categories: dict[int, BudgetAvailableCategory]
    assignable: Decimal
    future_assigned: Decimal


class EmergencyFundDetails(NamedTuple):
    """Type returned from get_emergency_fund."""

    spending_lower: list[Decimal]
    spending_upper: list[Decimal]
    balances: list[Decimal]
    categories: dict[int, tuple[str, str]]
    categories_total: dict[int, Decimal]


class BudgetGroup(Base):
    """Budget group model for storing a grouping of categories.

    Attributes:
        name: Group name
        position: Group position

    """

    __tablename__ = "budget_group"
    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)
    position: ORMInt = orm.mapped_column(unique=True)

    __table_args__ = (*string_column_args("name"),)

    @orm.validates("name")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field)


class BudgetAssignment(Base):
    """Budget assignment model for storing an contribution to a budget category.

    Attributes:
        month_ord: Date ordinal on which BudgetAssignment occurred (1st of month)
        amount: Amount contributed to budget category
        category_id: Budget category to contribute to

    """

    __tablename__ = "budget_assignment"
    __table_id__ = None

    month_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    __table_args__ = (
        UniqueConstraint("month_ord", "category_id"),
        Index("budget_assignment_category_id", "category_id"),
    )

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validate decimal fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_decimals(key, field)

    @classmethod
    def get_monthly_available(
        cls,
        month: datetime.date,
    ) -> BudgetAvailable:
        """Get available budget for a month.

        Args:
            month: Month to compute budget during

        Returns:
            (
                dict{TransactionCategory: BudgetAvailable},
                assignable,
                future_assigned,
            )

        """
        month_ord = month.toordinal()
        query = Account.query().where(Account.budgeted)

        accounts = {
            acct.id_: acct.name
            for acct in sql.yield_(query)
            if acct.do_include(month_ord)
        }

        # Starting balance
        query = TransactionSplit.query(
            func.sum(TransactionSplit.amount),
        ).where(
            TransactionSplit.account_id.in_(accounts),
            TransactionSplit.date_ord < month_ord,
        )
        starting_balance = sql.scalar(query) or Decimal()
        ending_balance = starting_balance
        total_available = Decimal()

        # Check all categories not INCOME
        query = TransactionCategory.query(TransactionCategory.id_).where(
            TransactionCategory.group != TransactionCategoryGroup.INCOME,
        )
        budget_categories = {t_cat_id for t_cat_id, in sql.yield_(query)}

        # Current month's assignment
        query = BudgetAssignment.query(
            BudgetAssignment.category_id,
            BudgetAssignment.amount,
        ).where(BudgetAssignment.month_ord == month_ord)
        categories_assigned: dict[int, Decimal] = sql.to_dict(query)

        # Prior months' assignment
        min_month_ord = month_ord
        prior_assigned: dict[int, dict[int, Decimal]] = {
            t_cat_id: {} for t_cat_id in budget_categories
        }
        query = (
            BudgetAssignment.query(
                BudgetAssignment.category_id,
                BudgetAssignment.amount,
                BudgetAssignment.month_ord,
            )
            .where(BudgetAssignment.month_ord < month_ord)
            .order_by(BudgetAssignment.month_ord)
        )
        for cat_id, amount, m_ord in sql.yield_(query):
            prior_assigned[cat_id][m_ord] = amount
            min_month_ord = min(min_month_ord, m_ord)

        # Prior months' activity
        prior_activity: dict[int, dict[int, Decimal]] = {
            t_cat_id: {} for t_cat_id in budget_categories
        }
        query = (
            TransactionSplit.query(
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
        for cat_id, amount, m_ord in sql.yield_(query):
            prior_activity[cat_id][m_ord] = amount

        # Carry over leftover to next months to get current month's leftover amounts
        categories_leftover: dict[int, Decimal] = defaultdict(Decimal)
        date = datetime.date.fromordinal(min_month_ord)
        while date < month:
            date_ord = date.toordinal()
            for t_cat_id in budget_categories:
                assigned = categories_leftover[t_cat_id] + prior_assigned[t_cat_id].get(
                    date_ord,
                    Decimal(),
                )
                activity = prior_activity[t_cat_id].get(date_ord, Decimal())
                leftover = assigned + activity
                categories_leftover[t_cat_id] = max(Decimal(), leftover)
            date = utils.date_add_months(date, 1)

        # Future months' assignment
        query = BudgetAssignment.query(func.sum(BudgetAssignment.amount)).where(
            BudgetAssignment.month_ord > month_ord,
        )
        future_assigned = sql.scalar(query) or Decimal()

        # Current month's activity
        query = (
            TransactionSplit.query(
                TransactionSplit.category_id,
                func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.month_ord == month_ord,
            )
            .group_by(TransactionSplit.category_id)
        )
        categories_activity: dict[int, Decimal] = sql.to_dict(query)

        categories: dict[int, BudgetAvailableCategory] = {}
        query = TransactionCategory.query(
            TransactionCategory.id_,
            TransactionCategory.group,
        )
        for t_cat_id, group in sql.yield_(query):
            activity = categories_activity.get(t_cat_id, Decimal())
            assigned = categories_assigned.get(t_cat_id, Decimal())
            leftover = categories_leftover.get(t_cat_id, Decimal())
            available = (
                Decimal()
                if group == TransactionCategoryGroup.INCOME
                else assigned + activity + leftover
            )

            ending_balance += activity
            total_available += available
            categories[t_cat_id] = BudgetAvailableCategory(
                assigned,
                activity,
                available,
                leftover,
            )

        assignable = ending_balance - total_available

        return BudgetAvailable(categories, assignable, future_assigned)

    @classmethod
    def get_emergency_fund(
        cls,
        start_ord: int,
        end_ord: int,
        n_lower: int,
        n_upper: int,
    ) -> EmergencyFundDetails:
        """Get the emergency fund target range and assigned balance.

        Args:
            start_ord: First day of calculated range
            end_ord: Last day of calculated range
            n_lower: Number of days in sliding lower period
            n_upper: Number of days in sliding upper period

        Returns:
            EmergencyFundDetails

        """
        n = end_ord - start_ord + 1
        n_smoothing = 15

        query = Account.query(Account.id_, Account.name).where(Account.budgeted)
        accounts: dict[int, str] = sql.to_dict(query)

        t_cat_id, _ = TransactionCategory.emergency_fund()

        query = BudgetAssignment.query(func.sum(BudgetAssignment.amount)).where(
            BudgetAssignment.category_id == t_cat_id,
            BudgetAssignment.month_ord <= start_ord,
        )
        balance = sql.scalar(query) or Decimal()

        balances: list[Decimal] = []

        query = (
            BudgetAssignment.query(BudgetAssignment.month_ord, BudgetAssignment.amount)
            .where(
                BudgetAssignment.category_id == t_cat_id,
                BudgetAssignment.month_ord > start_ord,
                BudgetAssignment.month_ord <= end_ord,
            )
            .order_by(BudgetAssignment.month_ord)
        )
        date_ord = start_ord
        for b_ord, amount in sql.yield_(query):
            while date_ord < b_ord:
                balances.append(balance)
                date_ord += 1
            balance += amount
        while date_ord <= end_ord:
            balances.append(balance)
            date_ord += 1

        categories: dict[int, tuple[str, str]] = {}
        categories_total: dict[int, Decimal] = {}

        daily = Decimal()
        dailys: list[Decimal] = []

        query = TransactionCategory.query(
            TransactionCategory.id_,
            TransactionCategory.name,
            TransactionCategory.emoji_name,
        ).where(TransactionCategory.essential_spending)
        for t_cat_id, name, emoji_name in sql.yield_(query):
            categories[t_cat_id] = name, emoji_name
            categories_total[t_cat_id] = Decimal()

        start_ord_dailys = start_ord - n_upper - n_smoothing
        query = (
            TransactionSplit.query(
                TransactionSplit.date_ord,
                TransactionSplit.category_id,
                func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.category_id.in_(categories),
                TransactionSplit.date_ord >= start_ord_dailys,
            )
            .group_by(TransactionSplit.date_ord, TransactionSplit.category_id)
        )
        date_ord = start_ord_dailys
        for t_ord, t_cat_id, amount in sql.yield_(query):
            while date_ord < t_ord:
                dailys.append(daily)
                date_ord += 1
                daily = Decimal()

            daily += amount

            if t_ord >= start_ord:
                categories_total[t_cat_id] += amount

        while date_ord <= end_ord:
            dailys.append(daily)
            date_ord += 1
            daily = Decimal()

        totals_lower: list[Decimal] = [
            Decimal(-sum(dailys[i : i + n_lower]))
            for i in range(len(dailys) - n_lower + 1)
        ]
        totals_upper: list[Decimal] = [
            Decimal(-sum(dailys[i : i + n_upper]))
            for i in range(len(dailys) - n_upper + 1)
        ]

        totals_lower = utils.low_pass(totals_lower, n_smoothing)
        totals_upper = utils.low_pass(totals_upper, n_smoothing)
        totals_lower = totals_lower[-n:]
        totals_upper = totals_upper[-n:]

        return EmergencyFundDetails(
            totals_lower,
            totals_upper,
            balances,
            categories,
            categories_total,
        )

    @classmethod
    def move(
        cls,
        month_ord: int,
        src_cat_id: int | None,
        dest_cat_id: int | None,
        to_move: Decimal,
    ) -> None:
        """Move funds between budget assignments.

        Args:
            month_ord: Month of BudgetAssignment
            src_cat_id: Source category ID, or None
            dest_cat_id: Destination category ID, or None
            to_move: Amount to move

        """
        if src_cat_id is not None:
            # Remove to_move from src_cat_id
            a = (
                BudgetAssignment.query()
                .where(
                    BudgetAssignment.category_id == src_cat_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one_or_none()
            )
            if a is None:
                BudgetAssignment.create(
                    month_ord=month_ord,
                    amount=-to_move,
                    category_id=src_cat_id,
                )
            elif a.amount == to_move:
                a.delete()
            else:
                a.amount -= to_move

        if dest_cat_id is not None:
            a = (
                BudgetAssignment.query()
                .where(
                    BudgetAssignment.category_id == dest_cat_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one_or_none()
            )
            if a is None:
                BudgetAssignment.create(
                    month_ord=month_ord,
                    amount=to_move,
                    category_id=dest_cat_id,
                )
            else:
                a.amount += to_move


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

    __tablename__ = "target"
    __table_id__ = 0x00000000

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
        Index("target_category_id", "category_id"),
    )

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validate decimal fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_decimals(key, field)

    @property
    def due_date(self) -> datetime.date | None:
        """Date on which target is due."""
        if self.due_date_ord is None:
            return None
        return datetime.date.fromordinal(self.due_date_ord)
