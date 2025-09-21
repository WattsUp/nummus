from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
import werkzeug.datastructures

from nummus.controllers import base, budgeting
from nummus.models import (
    BudgetAssignment,
    BudgetGroup,
    query_count,
    Target,
    TargetPeriod,
    TargetType,
    TransactionCategory,
)

if TYPE_CHECKING:
    import flask
    from sqlalchemy import orm

    from nummus.models import (
        Transaction,
    )
    from tests.controllers.conftest import WebClient


def test_page(month: datetime.date, web_client: WebClient) -> None:
    result, _ = web_client.GET("budgeting.page")
    assert "Budgeting" in result
    assert month.isoformat()[:7] in result
    assert "Available balance" in result


@pytest.mark.parametrize(
    ("prop", "value"),
    [
        ("date", "2100-01-01"),
        ("amount", "1"),
        ("repeat", "1"),
    ],
)
def test_validation(
    web_client: WebClient,
    prop: str,
    value: str,
) -> None:
    result, headers = web_client.GET(("budgeting.validation", {prop: value}))
    assert not result
    assert headers["HX-Trigger"] == "target-desc"


def test_assign_new(
    month: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    categories: dict[str, int],
    rand_real: Decimal,
) -> None:
    t_cat_id = categories["groceries"]
    t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)

    result, _ = web_client.PUT(
        ("budgeting.assign", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
        data={"amount": rand_real},
    )

    assert "Ungrouped" in result

    a = session.query(BudgetAssignment).one()
    assert a.category_id == t_cat_id
    assert a.month_ord == month.toordinal()
    assert a.amount == round(rand_real, 2)


def test_assign_edit(
    month: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    budget_assignments: list[BudgetAssignment],
) -> None:
    a = budget_assignments[0]
    t_cat_uri = TransactionCategory.id_to_uri(a.category_id)

    result, _ = web_client.PUT(
        ("budgeting.assign", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
        data={"amount": "10"},
    )

    assert "Ungrouped" in result

    session.refresh(a)
    assert a.month_ord == month.toordinal()
    assert a.amount == Decimal(10)


def test_assign_remove(
    month: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    budget_assignments: list[BudgetAssignment],
) -> None:
    a = budget_assignments[0]
    t_cat_uri = TransactionCategory.id_to_uri(a.category_id)

    result, _ = web_client.PUT(
        ("budgeting.assign", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
        data={"amount": 0},
    )

    assert "Ungrouped" in result

    a = (
        session.query(BudgetAssignment)
        .where(BudgetAssignment.id_ == a.id_)
        .one_or_none()
    )
    assert a is None


def test_move_get_income(
    month: datetime.date,
    web_client: WebClient,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    result, _ = web_client.GET(
        ("budgeting.move", {"uri": "income", "month": month.isoformat()[:7]}),
    )

    assert "Move available funds" in result
    assert "Assignable income has $1,170.00 available" in result
    assert "Groceries $30.00" in result


def test_move_get(
    month: datetime.date,
    web_client: WebClient,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    t_cat_uri = TransactionCategory.id_to_uri(categories["groceries"])

    result, _ = web_client.GET(
        ("budgeting.move", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
    )

    assert "Move available funds" in result
    assert "Groceries has $30.00 available" in result
    assert "Assignable income $1,170.00" in result


def test_move_get_destination(
    month: datetime.date,
    web_client: WebClient,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = transactions_spending
    _ = budget_assignments
    t_cat_uri = TransactionCategory.id_to_uri(categories["groceries"])

    result, _ = web_client.GET(
        (
            "budgeting.move",
            {"uri": "income", "month": month.isoformat()[:7], "destination": t_cat_uri},
        ),
    )

    assert "Move available funds" in result
    assert "Assignable income has $1,170.00 available" in result
    assert f'value="{t_cat_uri}" selected' in result


def test_move_get_overspending(
    month: datetime.date,
    web_client: WebClient,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    _ = transactions_spending
    t_cat_uri = TransactionCategory.id_to_uri(categories["groceries"])

    result, _ = web_client.GET(
        ("budgeting.move", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
    )

    assert "Cover overspending" in result
    assert "Groceries is overspent by $20.00" in result
    assert "Assignable income $1,320.00" in result


def test_move_overspending(
    month: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
    categories: dict[str, int],
) -> None:
    _ = transactions_spending
    a = budget_assignments[0]
    uri = TransactionCategory.id_to_uri(categories["securities traded"])
    dest_uri = TransactionCategory.id_to_uri(a.category_id)

    result, headers = web_client.PUT(
        ("budgeting.move", {"uri": uri, "month": month.isoformat()[:7]}),
        data={"destination": dest_uri},
    )
    assert "snackbar.show" in result
    assert "$30.00 reallocated" in result
    assert headers["HX-Trigger"] == "budget"

    session.refresh(a)
    assert a.month_ord == month.toordinal()
    assert a.amount == Decimal(20)


def test_move_to_income(
    month: datetime.date,
    session: orm.Session,
    web_client: WebClient,
    transactions_spending: list[Transaction],
    budget_assignments: list[BudgetAssignment],
) -> None:
    _ = transactions_spending
    a = budget_assignments[0]
    t_cat_uri = TransactionCategory.id_to_uri(a.category_id)

    result, headers = web_client.PUT(
        ("budgeting.move", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
        data={"destination": "income", "amount": "10"},
    )
    assert "snackbar.show" in result
    assert "$10.00 reallocated" in result
    assert headers["HX-Trigger"] == "budget"

    session.refresh(a)
    assert a.month_ord == month.toordinal()
    assert a.amount == Decimal(40)


def test_move_error(
    month: datetime.date,
    web_client: WebClient,
    budget_assignments: list[BudgetAssignment],
) -> None:
    a = budget_assignments[0]
    t_cat_uri = TransactionCategory.id_to_uri(a.category_id)

    result, _ = web_client.PUT(
        ("budgeting.move", {"uri": t_cat_uri, "month": month.isoformat()[:7]}),
        data={"destination": "income", "amount": ""},
    )
    assert result == base.error("Amount to move must not be blank")


def test_reorder_empty(
    session: orm.Session,
    web_client: WebClient,
    budget_group: BudgetGroup,
) -> None:
    _ = budget_group
    result, _ = web_client.PUT(
        "budgeting.reorder",
        data={
            "group-uri": [],
            "category-uri": [],
            "group": [],
        },
    )
    assert not result

    query = session.query(BudgetGroup)
    assert query_count(query) == 0
    query = session.query(TransactionCategory).where(
        TransactionCategory.budget_group_id.is_not(None),
    )
    assert query_count(query) == 0
    query = session.query(TransactionCategory).where(
        TransactionCategory.budget_position.is_not(None),
    )
    assert query_count(query) == 0


def test_reorder(
    session: orm.Session,
    web_client: WebClient,
    budget_group: BudgetGroup,
) -> None:
    t_cat_0 = (
        session.query(TransactionCategory)
        .where(TransactionCategory.name == "groceries")
        .one()
    )
    t_cat_1 = (
        session.query(TransactionCategory)
        .where(TransactionCategory.name == "rent")
        .one()
    )
    t_cat_2 = (
        session.query(TransactionCategory)
        .where(TransactionCategory.name == "transfers")
        .one()
    )

    result, _ = web_client.PUT(
        "budgeting.reorder",
        data={
            "group-uri": [budget_group.uri],
            "category-uri": [t_cat_0.uri, t_cat_1.uri, t_cat_2.uri],
            "group": [budget_group.uri, budget_group.uri, "ungrouped"],
        },
    )
    assert not result

    session.refresh(t_cat_0)
    assert t_cat_0.budget_group_id == budget_group.id_
    assert t_cat_0.budget_position == 0

    session.refresh(t_cat_1)
    assert t_cat_1.budget_group_id == budget_group.id_
    assert t_cat_1.budget_position == 1

    session.refresh(t_cat_2)
    assert t_cat_2.budget_group_id is None
    assert t_cat_2.budget_position is None


def test_group_open(web_client: WebClient) -> None:
    result, _ = web_client.PUT(
        ("budgeting.group", {"uri": "ungrouped"}),
        data={"open": ""},
    )
    assert not result
    with web_client.session() as session:
        assert session["groups_open"] == ["ungrouped"]


def test_group_close(web_client: WebClient) -> None:
    with web_client.session() as session:
        session["groups_open"] = ["ungrouped"]

    result, _ = web_client.PUT(
        ("budgeting.group", {"uri": "ungrouped"}),
        data={},
    )
    assert not result
    with web_client.session() as session:
        assert session["groups_open"] == []


def test_group(
    session: orm.Session,
    web_client: WebClient,
    budget_group: BudgetGroup,
    rand_str: str,
) -> None:
    result, _ = web_client.PUT(
        ("budgeting.group", {"uri": budget_group.uri}),
        data={"name": rand_str},
    )
    assert not result

    session.refresh(budget_group)
    assert budget_group.name == rand_str


def test_group_error_income(web_client: WebClient) -> None:
    web_client.PUT(
        ("budgeting.group", {"uri": "ungrouped"}),
        data={"name": "a"},
        rc=base.HTTP_CODE_BAD_REQUEST,
    )


def test_group_error(web_client: WebClient, budget_group: BudgetGroup) -> None:
    result, _ = web_client.PUT(
        ("budgeting.group", {"uri": budget_group.uri}),
        data={"name": "a"},
    )
    assert result == base.error("Budget group name must be at least 2 characters long")


def test_new_group(web_client: WebClient) -> None:
    result, _ = web_client.POST("budgeting.new_group")
    assert '"New group"' in result
    assert '"New group 2"' not in result


def test_new_group_second(web_client: WebClient) -> None:
    web_client.POST("budgeting.new_group")
    result, _ = web_client.POST("budgeting.new_group")
    assert '"New group"' not in result
    assert '"New group 2"' in result


@pytest.mark.parametrize(
    ("kwargs", "period", "type_", "due", "repeat_every"),
    [
        ({}, TargetPeriod.MONTH, TargetType.ACCUMULATE, True, 1),
        (
            {"due": "2100-01-01"},
            TargetPeriod.MONTH,
            TargetType.ACCUMULATE,
            "2100-01-01",
            1,
        ),
        ({"repeat": "2"}, TargetPeriod.MONTH, TargetType.ACCUMULATE, True, 2),
        (
            {"period": "Weekly", "change": "on"},
            TargetPeriod.WEEK,
            TargetType.ACCUMULATE,
            0,
            1,
        ),
        (
            {"period": "Once"},
            TargetPeriod.ONCE,
            TargetType.BALANCE,
            True,
            0,
        ),
        (
            {"period": "Once", "has-due": "off"},
            TargetPeriod.ONCE,
            TargetType.BALANCE,
            False,
            0,
        ),
        (
            {"period": "Once", "has-due": "on", "due-year": "2100", "due-month": "1"},
            TargetPeriod.ONCE,
            TargetType.BALANCE,
            "2100-01-01",
            0,
        ),
    ],
)
def test_parse_form(
    today: datetime.date,
    today_ord: int,
    flask_app: flask.Flask,
    kwargs: dict[str, str | list[str]],
    period: TargetPeriod,
    type_: TargetType,
    due: bool | str | int,
    repeat_every: int,
) -> None:
    target = Target(
        amount=0,
        type_=TargetType.ACCUMULATE,
        period=TargetPeriod.MONTH,
        due_date_ord=today_ord,
        repeat_every=1,
    )
    args = werkzeug.datastructures.MultiDict(kwargs)

    with flask_app.test_request_context():
        budgeting.parse_target_form(target, args)

    assert target.period == period
    assert target.type_ == type_
    if isinstance(due, str):
        assert target.due_date_ord == datetime.date.fromisoformat(due).toordinal()
    elif isinstance(due, bool):
        if due:
            assert target.due_date_ord == today_ord
        else:
            assert target.due_date_ord is None
    else:
        due_date = today + datetime.timedelta(
            days=int(due) - today.weekday(),
        )
        assert target.due_date_ord == due_date.toordinal()
    assert target.repeat_every == repeat_every


def test_target_get_new(web_client: WebClient, categories: dict[str, int]) -> None:
    t_cat_uri = TransactionCategory.id_to_uri(categories["groceries"])
    result, _ = web_client.GET(("budgeting.target", {"uri": t_cat_uri}))
    assert "New target" in result


def test_target_get(web_client: WebClient, budget_target: Target) -> None:
    result, _ = web_client.GET(("budgeting.target", {"uri": budget_target.uri}))
    assert "Edit target" in result


def test_target_get_once(
    today_ord: int,
    session: orm.Session,
    web_client: WebClient,
    budget_target: Target,
) -> None:
    budget_target.type_ = TargetType.BALANCE
    budget_target.period = TargetPeriod.ONCE
    budget_target.due_date_ord = today_ord
    session.commit()

    result, _ = web_client.GET(("budgeting.target", {"uri": budget_target.uri}))
    assert "Edit target" in result


def test_target_new(
    today_ord: int,
    session: orm.Session,
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    t_cat_id = categories["groceries"]
    t_cat_uri = TransactionCategory.id_to_uri(t_cat_id)

    result, headers = web_client.POST(
        ("budgeting.target", {"uri": t_cat_uri}),
        data={"amount": "10"},
    )

    assert "snackbar.show" in result
    assert "Groceries target created" in result
    assert headers["HX-Trigger"] == "budget"

    tar = session.query(Target).one()
    assert tar.category_id == t_cat_id
    assert tar.amount == Decimal(10)
    assert tar.type_ == TargetType.ACCUMULATE
    assert tar.period == TargetPeriod.MONTH
    assert tar.due_date_ord == today_ord
    assert tar.repeat_every == 1


def test_target_new_duplicate(
    web_client: WebClient,
    budget_target: Target,
) -> None:
    result, _ = web_client.POST(("budgeting.target", {"uri": budget_target.uri}))
    assert result == base.error("Cannot have multiple targets per category")


def test_target_new_error(
    web_client: WebClient,
    categories: dict[str, int],
) -> None:
    t_cat_uri = TransactionCategory.id_to_uri(categories["groceries"])
    result, _ = web_client.POST(("budgeting.target", {"uri": t_cat_uri}))
    assert result == base.error("Target amount must be positive")


def test_target_put(
    session: orm.Session,
    web_client: WebClient,
    budget_target: Target,
) -> None:
    result, headers = web_client.PUT(
        ("budgeting.target", {"uri": budget_target.uri}),
        data={"amount": "10"},
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "budget"

    session.refresh(budget_target)
    assert budget_target.amount == Decimal(10)


def test_target_delete(
    session: orm.Session,
    web_client: WebClient,
    budget_target: Target,
) -> None:
    result, headers = web_client.DELETE(
        ("budgeting.target", {"uri": budget_target.uri}),
    )
    assert "snackbar.show" in result
    assert "Emergency Fund target deleted" in result
    assert headers["HX-Trigger"] == "budget"

    tar = session.query(Target).one_or_none()
    assert tar is None


def test_sidebar(month: datetime.date, web_client: WebClient) -> None:
    result, headers = web_client.GET("budgeting.sidebar")
    assert "Available balance" in result
    assert "Targets" in result
    url = web_client.url_for("budgeting.page", month=month.isoformat()[:7])
    assert headers["HX-Push-URL"] == url
