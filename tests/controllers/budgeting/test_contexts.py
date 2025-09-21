from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.controllers import budgeting
from nummus.models import (
    BudgetAssignment,
    TargetPeriod,
    TargetType,
    TransactionCategory,
)
from nummus.models.transaction_category import TransactionCategoryGroup

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import (
        BudgetGroup,
        Target,
        Transaction,
    )


def test_ctx_sidebar_global(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    budget_target: Target,
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    _ = budget_target
    data = BudgetAssignment.get_monthly_available(session, month)

    ctx = budgeting.ctx_sidebar(
        session,
        today,
        month,
        data.categories,
        data.future_assigned,
        None,
    )

    query = session.query(TransactionCategory).where(
        TransactionCategory.name.not_in({"emergency fund"}),
        TransactionCategory.group != TransactionCategoryGroup.INCOME,
    )
    categories = {t_cat.uri: t_cat.emoji_name for t_cat in query.all()}

    target: budgeting.SidebarContext = {
        "uri": None,
        "name": None,
        "month": month.isoformat()[:7],
        "available": Decimal(30),
        "leftover": Decimal(),
        "assigned": Decimal(150),
        "future_assigned": Decimal(2000),
        "activity": Decimal(-120),
        "to_go": Decimal(900),
        "no_target": categories,
        "target": None,
    }
    assert ctx == target


def test_ctx_sidebar_no_target(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    categories: dict[str, int],
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    data = BudgetAssignment.get_monthly_available(session, month)
    uri = TransactionCategory.id_to_uri(categories["emergency fund"])

    ctx = budgeting.ctx_sidebar(
        session,
        today,
        month,
        data.categories,
        data.future_assigned,
        uri,
    )

    target: budgeting.SidebarContext = {
        "uri": uri,
        "name": "Emergency Fund",
        "month": month.isoformat()[:7],
        "available": Decimal(100),
        "leftover": Decimal(),
        "assigned": Decimal(100),
        "future_assigned": None,
        "activity": Decimal(),
        "target": None,
    }
    assert ctx == target


def test_ctx_sidebar(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    budget_target: Target,
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    data = BudgetAssignment.get_monthly_available(session, month)
    data_cat = data.categories[budget_target.category_id]
    uri = TransactionCategory.id_to_uri(budget_target.category_id)

    ctx = budgeting.ctx_sidebar(
        session,
        today,
        month,
        data.categories,
        data.future_assigned,
        uri,
    )

    target: budgeting.SidebarContext = {
        "uri": uri,
        "name": "Emergency Fund",
        "month": month.isoformat()[:7],
        "available": Decimal(100),
        "leftover": Decimal(),
        "assigned": Decimal(100),
        "future_assigned": None,
        "activity": Decimal(),
        "target": budgeting.ctx_target(
            budget_target,
            today,
            month,
            data_cat.assigned,
            data_cat.available,
            data_cat.leftover,
        ),
    }
    assert ctx == target


def test_ctx_target_no_due_date(
    today: datetime.date,
    month: datetime.date,
    budget_target: Target,
) -> None:
    ctx = budgeting.ctx_target(
        budget_target,
        today,
        month,
        Decimal(100),
        Decimal(200),
        Decimal(100),
    )

    target: budgeting.TargetContext = {
        "target_assigned": Decimal(900),
        "total_assigned": Decimal(200),
        "to_go": Decimal(800),
        "on_track": False,
        "next_due_date": None,
        "progress_bars": [Decimal(1000)],
        "target": Decimal(1000),
        "total_target": Decimal(1000),
        "total_to_go": Decimal(800),
        "period": budget_target.period,
        "type": budget_target.type_,
    }
    assert ctx == target


def test_ctx_target_once(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    budget_target: Target,
) -> None:
    due_date = utils.date_add_months(month, 8)
    budget_target.due_date_ord = due_date.toordinal()
    session.commit()

    ctx = budgeting.ctx_target(
        budget_target,
        today,
        month,
        Decimal(100),
        Decimal(200),
        Decimal(100),
    )

    target: budgeting.TargetContext = {
        "target_assigned": Decimal(100),
        "total_assigned": Decimal(200),
        "to_go": Decimal(),
        "on_track": True,
        "next_due_date": f"{due_date:%B %Y}",
        "progress_bars": [Decimal(1000)],
        "target": Decimal(1000),
        "total_target": Decimal(1000),
        "total_to_go": Decimal(800),
        "period": budget_target.period,
        "type": budget_target.type_,
    }
    assert ctx == target


def test_ctx_target_weekly_refil(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    budget_target: Target,
) -> None:
    month = utils.date_add_months(month, 1)
    budget_target.period = TargetPeriod.WEEK
    budget_target.type_ = TargetType.REFILL
    budget_target.due_date_ord = today.toordinal()
    budget_target.repeat_every = 1
    session.commit()
    n_weekdays = utils.weekdays_in_month(today.weekday(), month)

    ctx = budgeting.ctx_target(
        budget_target,
        today,
        month,
        Decimal(100),
        Decimal(200),
        Decimal(100),
    )

    target: budgeting.TargetContext = {
        "target_assigned": Decimal(1000) * n_weekdays - 100,
        "total_assigned": Decimal(200),
        "to_go": Decimal(1000) * n_weekdays - 200,
        "on_track": False,
        "next_due_date": utils.WEEKDAYS[today.weekday()],
        "progress_bars": [Decimal(1000)] * n_weekdays,
        "target": Decimal(1000),
        "total_target": Decimal(1000) * n_weekdays,
        "total_to_go": Decimal(1000) * n_weekdays - 200,
        "period": budget_target.period,
        "type": budget_target.type_,
    }
    assert ctx == target


def test_ctx_target_weekly_accumulate(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    budget_target: Target,
) -> None:
    budget_target.period = TargetPeriod.WEEK
    budget_target.type_ = TargetType.ACCUMULATE
    budget_target.due_date_ord = today.toordinal()
    budget_target.repeat_every = 1
    session.commit()
    n_weekdays = utils.weekdays_in_month(today.weekday(), month)

    ctx = budgeting.ctx_target(
        budget_target,
        today,
        month,
        Decimal(100),
        Decimal(200),
        Decimal(100),
    )

    target: budgeting.TargetContext = {
        "target_assigned": Decimal(1000) * n_weekdays,
        "total_assigned": Decimal(100),
        "to_go": Decimal(1000) * n_weekdays - 100,
        "on_track": False,
        "next_due_date": utils.WEEKDAYS[today.weekday()],
        "progress_bars": [Decimal(100)] + [Decimal(1000)] * n_weekdays,
        "target": Decimal(1000),
        "total_target": Decimal(1000) * n_weekdays,
        "total_to_go": Decimal(1000) * n_weekdays - 100,
        "period": budget_target.period,
        "type": budget_target.type_,
    }
    assert ctx == target


def test_ctx_target_monthly_refil(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    budget_target: Target,
) -> None:
    month = utils.date_add_months(month, 1)
    budget_target.period = TargetPeriod.MONTH
    budget_target.type_ = TargetType.REFILL
    budget_target.due_date_ord = today.toordinal()
    budget_target.repeat_every = 2
    session.commit()

    ctx = budgeting.ctx_target(
        budget_target,
        today,
        month,
        Decimal(100),
        Decimal(200),
        Decimal(100),
    )

    target: budgeting.TargetContext = {
        "target_assigned": Decimal(450),
        "total_assigned": Decimal(200),
        "to_go": Decimal(350),
        "on_track": False,
        "next_due_date": utils.date_add_months(today, 2),
        "progress_bars": [Decimal(1000)],
        "target": Decimal(1000),
        "total_target": Decimal(1000),
        "total_to_go": Decimal(1000) - 200,
        "period": budget_target.period,
        "type": budget_target.type_,
    }
    assert ctx == target


def test_ctx_target_monthly_accumulate(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    budget_target: Target,
) -> None:
    budget_target.period = TargetPeriod.MONTH
    budget_target.type_ = TargetType.ACCUMULATE
    budget_target.due_date_ord = today.toordinal()
    budget_target.repeat_every = 1
    session.commit()

    ctx = budgeting.ctx_target(
        budget_target,
        today,
        month,
        Decimal(100),
        Decimal(200),
        Decimal(100),
    )

    target: budgeting.TargetContext = {
        "target_assigned": Decimal(1000),
        "total_assigned": Decimal(100),
        "to_go": Decimal(900),
        "on_track": False,
        "next_due_date": today,
        "progress_bars": [Decimal(100), Decimal(1000)],
        "target": Decimal(1000),
        "total_target": Decimal(1000),
        "total_to_go": Decimal(1000) - 100,
        "period": budget_target.period,
        "type": budget_target.type_,
    }
    assert ctx == target


def test_ctx_budget_empty(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
) -> None:
    data = BudgetAssignment.get_monthly_available(session, month)
    ctx, title = budgeting.ctx_budget(
        session,
        today,
        month,
        data.categories,
        data.assignable,
        [],
    )

    month_str = month.isoformat()[:7]
    assert title == f"Budgeting {month_str}"

    assert ctx["month"] == month_str
    assert ctx["month_next"] == utils.date_add_months(month, 1).isoformat()[:7]
    assert ctx["month_prev"] == utils.date_add_months(month, -1).isoformat()[:7]
    assert ctx["assignable"] == Decimal()
    assert ctx["n_overspent"] == 0
    assert len(ctx["groups"]) == 1

    group = ctx["groups"][-1]
    assert group["activity"] == Decimal()
    assert group["assigned"] == Decimal()
    assert group["available"] == Decimal()
    assert not group["has_error"]
    assert not group["is_open"]
    assert group["name"] is None
    assert group["position"] == -1
    assert group["uri"] is None
    unhidden = [cat for cat in group["categories"] if not cat["hidden"]]
    assert unhidden == []


def test_ctx_budget(
    today: datetime.date,
    month: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    budget_group: BudgetGroup,
    budget_target: Target,
    categories: dict[str, int],
) -> None:
    session.query(TransactionCategory).where(
        TransactionCategory.name == "groceries",
    ).update(
        {
            TransactionCategory.budget_group_id: budget_group.id_,
            TransactionCategory.budget_position: 0,
        },
    )
    session.commit()
    _ = transactions_spending
    _ = budget_assignments
    data = BudgetAssignment.get_monthly_available(session, month)

    ctx, title = budgeting.ctx_budget(
        session,
        today,
        month,
        data.categories,
        data.assignable,
        [],
    )

    month_str = month.isoformat()[:7]
    assert title == f"Budgeting {month_str}"

    assert ctx["month"] == month_str
    assert ctx["month_next"] == utils.date_add_months(month, 1).isoformat()[:7]
    assert ctx["month_prev"] == utils.date_add_months(month, -1).isoformat()[:7]
    assert ctx["assignable"] == Decimal(1170)
    assert ctx["n_overspent"] == 2
    assert len(ctx["groups"]) == 2

    group = ctx["groups"][0]
    assert group["activity"] == Decimal(-20)
    assert group["assigned"] == Decimal(50)
    assert group["available"] == Decimal(30)
    assert not group["has_error"]
    assert not group["is_open"]
    assert group["name"] == budget_group.name
    assert group["position"] == 0
    assert group["uri"] == budget_group.uri
    target: list[budgeting.CategoryContext] = [
        {
            "name": "groceries",
            "emoji_name": "Groceries",
            "hidden": False,
            "position": 0,
            "target": None,
            "uri": TransactionCategory.id_to_uri(categories["groceries"]),
            "activity": Decimal(-20),
            "assigned": Decimal(50),
            "available": Decimal(30),
            "bars": [budgeting.ProgressBar(Decimal(1), Decimal(1), Decimal("0.4"))],
        },
    ]
    assert group["categories"] == target

    group = ctx["groups"][-1]
    assert group["activity"] == Decimal(-100)
    assert group["assigned"] == Decimal(100)
    assert group["available"] == Decimal()
    assert group["has_error"]
    assert not group["is_open"]
    assert group["name"] is None
    assert group["position"] == -1
    assert group["uri"] is None
    unhidden = [cat for cat in group["categories"] if not cat["hidden"]]
    target: list[budgeting.CategoryContext] = [
        {
            "name": "emergency fund",
            "emoji_name": "Emergency Fund",
            "hidden": False,
            "position": None,
            "target": budgeting.ctx_target(
                budget_target,
                today,
                month,
                Decimal(100),
                Decimal(100),
                Decimal(),
            ),
            "uri": TransactionCategory.id_to_uri(categories["emergency fund"]),
            "activity": Decimal(),
            "assigned": Decimal(100),
            "available": Decimal(100),
            "bars": [budgeting.ProgressBar(Decimal(1), Decimal("0.1"), Decimal(0))],
        },
        {
            "name": "rent",
            "emoji_name": "Rent",
            "hidden": False,
            "position": None,
            "target": None,
            "uri": TransactionCategory.id_to_uri(categories["rent"]),
            "activity": Decimal(-50),
            "assigned": Decimal(),
            "available": Decimal(-50),
            "bars": [budgeting.ProgressBar(Decimal(1), Decimal(1), Decimal(0))],
        },
        {
            "name": "securities traded",
            "emoji_name": "Securities Traded",
            "hidden": False,
            "position": None,
            "target": None,
            "uri": TransactionCategory.id_to_uri(categories["securities traded"]),
            "activity": Decimal(-50),
            "assigned": Decimal(),
            "available": Decimal(-50),
            "bars": [budgeting.ProgressBar(Decimal(1), Decimal(1), Decimal(0))],
        },
    ]
    assert unhidden == target


@pytest.mark.parametrize(
    ("available", "activity", "bar_dollars", "target"),
    [
        (Decimal(), Decimal(), [], []),
        (
            Decimal(),
            Decimal(),
            [Decimal()],
            [budgeting.ProgressBar(Decimal(1), Decimal(0), Decimal(0))],
        ),
        (
            Decimal(0),
            Decimal(-10),
            [Decimal(10)],
            [budgeting.ProgressBar(Decimal(1), Decimal(1), Decimal(1))],
        ),
        (
            Decimal(5),
            Decimal(-5),
            [Decimal(10)],
            [budgeting.ProgressBar(Decimal(1), Decimal(1), Decimal("0.5"))],
        ),
        (
            Decimal(-5),
            Decimal(-5),
            [Decimal(10)],
            [budgeting.ProgressBar(Decimal(1), Decimal("0.5"), Decimal(0))],
        ),
        (
            Decimal(95),
            Decimal(-5),
            [Decimal(10), Decimal(10)],
            [
                budgeting.ProgressBar(Decimal("0.1"), Decimal(1), Decimal("0.5")),
                budgeting.ProgressBar(Decimal("0.9"), Decimal(1), Decimal(0)),
            ],
        ),
    ],
)
def test_ctx_progress_bars(
    available: Decimal,
    activity: Decimal,
    bar_dollars: list[Decimal],
    target: list[budgeting.ProgressBar],
) -> None:
    result = budgeting.ctx_progress_bars(available, activity, bar_dollars)
    assert result == target
