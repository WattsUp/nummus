"""Budget model for storing an allocation of expenses per month."""

from __future__ import annotations

import datetime
from collections import defaultdict
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

    __table_id__ = 0x00000000

    name: ORMStr = orm.mapped_column(unique=True)
    position: ORMInt = orm.mapped_column(unique=True)

    __table_args__ = (*string_column_args("name"),)

    @orm.validates("name")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints.

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

    __table_id__ = None

    month_ord: ORMInt
    amount: ORMReal = orm.mapped_column(Decimal6)
    category_id: ORMInt = orm.mapped_column(ForeignKey("transaction_category.id_"))

    __table_args__ = (UniqueConstraint("month_ord", "category_id"),)

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimal fields satisfy constraints.

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
        categories_leftover: dict[int, Decimal] = defaultdict(Decimal)
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

    @classmethod
    def get_emergency_fund(
        cls,
        s: orm.Session,
        start_ord: int,
        end_ord: int,
        n_lower: int,
        n_upper: int,
    ) -> tuple[
        list[Decimal],
        list[Decimal],
        list[Decimal],
        dict[int, tuple[str, str]],
        dict[int, Decimal],
    ]:
        """Get the emergency fund target range and assigned balance.

        Args:
            s: SQL session to use
            start_ord: First day of calculated range
            end_ord: Last day of calculated range
            n_lower: Number of days in sliding lower period
            n_upper: Number of days in sliding upper period

        Returns:
            tuple(
                total spending in lower period,
                total spending in upper period,
                balances,
                categories,
                categories_total,
            )
        """
        n = end_ord - start_ord + 1
        n_smoothing = 15

        accounts: dict[int, str] = dict(
            s.query(Account)  # type: ignore[attr-defined]
            .with_entities(Account.id_, Account.name)
            .where(Account.budgeted)
            .all(),
        )

        t_cat_id, _ = TransactionCategory.emergency_fund(s)

        balance = s.query(func.sum(BudgetAssignment.amount)).where(
            BudgetAssignment.category_id == t_cat_id,
            BudgetAssignment.month_ord <= start_ord,
        ).scalar() or Decimal(0)

        balances: list[Decimal] = []

        query = (
            s.query(BudgetAssignment)
            .with_entities(BudgetAssignment.month_ord, BudgetAssignment.amount)
            .where(
                BudgetAssignment.category_id == t_cat_id,
                BudgetAssignment.month_ord > start_ord,
                BudgetAssignment.month_ord <= end_ord,
            )
            .order_by(BudgetAssignment.month_ord)
        )
        date_ord = start_ord
        for b_ord, amount in query.all():
            while date_ord < b_ord:
                balances.append(balance)
                date_ord += 1
            balance += amount
        while date_ord <= end_ord:
            balances.append(balance)
            date_ord += 1

        categories: dict[int, tuple[str, str]] = {}
        categories_total: dict[int, Decimal] = {}

        daily = Decimal(0)
        dailys: list[Decimal] = []

        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.name,
                TransactionCategory.emoji_name,
            )
            .where(TransactionCategory.essential)
        )
        for t_cat_id, name, emoji_name in query.all():
            categories[t_cat_id] = name, emoji_name
            categories_total[t_cat_id] = Decimal(0)

        start_ord_dailys = start_ord - n_upper - n_smoothing
        query = (
            s.query(TransactionSplit)
            .with_entities(
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
        for t_ord, t_cat_id, amount in query.yield_per(YIELD_PER):
            while date_ord < t_ord:
                dailys.append(daily)
                date_ord += 1
                daily = Decimal(0)

            daily += amount

            if t_ord >= start_ord:
                categories_total[t_cat_id] += amount

        while date_ord <= end_ord:
            dailys.append(daily)
            date_ord += 1
            daily = Decimal(0)

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

        return totals_lower, totals_upper, balances, categories, categories_total

    @classmethod
    def move(
        cls,
        s: orm.Session,
        month_ord: int,
        src_cat_id: int | None,
        dest_cat_id: int | None,
        to_move: Decimal,
    ) -> None:
        """Move funds between budget assignments.

        Args:
            s: SQL session to use
            month_ord: Month of BudgetAssignment
            src_cat_id: Source category ID, or None
            dest_cat_id: Destination category ID, or None
            to_move: Amount to move
        """
        if src_cat_id is not None:
            # Remove to_move from src_cat_id
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == src_cat_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one_or_none()
            )
            if a is None:
                a = BudgetAssignment(
                    month_ord=month_ord,
                    amount=-to_move,
                    category_id=src_cat_id,
                )
                s.add(a)
            elif a.amount == to_move:
                s.delete(a)
            else:
                a.amount -= to_move

        if dest_cat_id is not None:
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.category_id == dest_cat_id,
                    BudgetAssignment.month_ord == month_ord,
                )
                .one_or_none()
            )
            if a is None:
                a = BudgetAssignment(
                    month_ord=month_ord,
                    amount=to_move,
                    category_id=dest_cat_id,
                )
                s.add(a)
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
    )

    @orm.validates("amount")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimal fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field
        """
        return self.clean_decimals(key, field)
