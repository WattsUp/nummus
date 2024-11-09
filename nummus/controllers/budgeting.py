"""Budgeting controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import sql

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import TransactionCategory, TransactionCategoryGroup, YIELD_PER
from nummus.models.budget import BudgetAssignment, BudgetGroup

if TYPE_CHECKING:

    from nummus.controllers.base import Routes


def ctx_table(month: datetime.date | None = None) -> tuple[dict[str, object], str]:
    """Get the context to build the budgeting table.

    Args:
        month: Month of table, None will check request args

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    if month is None:
        month_str = args.get("month")
        month = (
            utils.start_of_month(datetime.date.today())
            if month_str is None
            else datetime.date.fromisoformat(month_str + "-01")
        )

    class CategoryContext(TypedDict):
        """Type definition for budget category context."""

        position: int | None
        name: str
        uri: str
        emoji_name: str
        assigned: Decimal
        activity: Decimal
        available: Decimal
        bar_mode: str
        bar_w: Decimal

    class GroupContext(TypedDict):
        """Type definition for budget group context."""

        position: int
        name: str | None
        uri: str | None
        categories: list[CategoryContext]
        assigned: Decimal
        activity: Decimal
        available: Decimal

    with p.get_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        n_overspent = 0

        groups: dict[int | None, GroupContext] = {}
        query = s.query(BudgetGroup)
        for g in query.all():
            groups[g.id_] = {
                "position": g.position,
                "name": g.name,
                "uri": g.uri,
                "assigned": Decimal(0),
                "activity": Decimal(0),
                "available": Decimal(0),
                "categories": [],
            }
        ungrouped: GroupContext = {
            "position": -1,
            "name": None,
            "uri": None,
            "assigned": Decimal(0),
            "activity": Decimal(0),
            "available": Decimal(0),
            "categories": [],
        }

        query = s.query(TransactionCategory)
        for t_cat in query.yield_per(YIELD_PER):
            assigned, activity, available = categories[t_cat.id_]
            # Skip category if all numbers are 0 and not grouped
            if (
                t_cat.budget_group_id is None
                and activity == 0
                and assigned == 0
                and available == 0
            ):
                continue
            if t_cat.group == TransactionCategoryGroup.INCOME:
                continue

            if available < 0:
                n_overspent += 1

            if activity == 0 and available == 0:
                bar_mode = "grey"
                bar_w = Decimal(0)
            elif available >= 0:
                bar_mode = "funded"
                bar_w = (
                    Decimal(0)
                    if activity > 0
                    else -activity / (available - activity) * 100
                )
            else:
                bar_mode = "underfunded"
                bar_w = (
                    Decimal(0)
                    if available < activity
                    else (activity - available) / activity * 100
                )

            cat_ctx: CategoryContext = {
                "position": t_cat.budget_position,
                "uri": t_cat.uri,
                "name": t_cat.name,
                "emoji_name": t_cat.emoji_name,
                "assigned": assigned,
                "activity": activity,
                "available": available,
                "bar_mode": bar_mode,
                "bar_w": bar_w,
            }
            g = groups.get(t_cat.budget_group_id, ungrouped)
            g["assigned"] += assigned
            g["activity"] += activity
            g["available"] += available
            g["categories"].append(cat_ctx)

        groups_list = sorted(groups.values(), key=lambda item: item["position"])
        groups_list.append(ungrouped)

        for g in groups_list:
            g["categories"] = sorted(
                g["categories"],
                key=lambda item: (item["position"] or 0, item["name"]),
            )

    month_str = month.isoformat()[:7]
    title = f"Budgeting { month_str} | nummus"
    return {
        "month": month_str,
        "month_next": utils.date_add_months(month, 1).isoformat()[:7],
        "month_prev": utils.date_add_months(month, -1).isoformat()[:7],
        "assignable": assignable,
        "future_assigned": future_assigned,
        "groups": groups_list,
        "n_overspent": n_overspent,
    }, title


def page() -> str:
    """GET /budgeting.

    Returns:
        string HTML response
    """
    table, title = ctx_table()
    return common.page(
        "budgeting/index-content.jinja",
        title=title,
        table=table,
    )


def assign(uri: str) -> str:
    """PUT /h/budgeting/c/<path:uri>/assign.

    Args:
        uri: Category URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    month_str = args["month"]
    month = datetime.date.fromisoformat(month_str + "-01")
    month_ord = month.toordinal()

    form = flask.request.form
    amount = utils.parse_real(form.get("amount")) or Decimal(0)

    with p.get_session() as s:
        cat = web_utils.find(s, TransactionCategory, uri)
        if amount == 0:
            s.query(BudgetAssignment).where(
                BudgetAssignment.month_ord == month_ord,
                BudgetAssignment.category_id == cat.id_,
            ).delete()
        else:
            a = (
                s.query(BudgetAssignment)
                .where(
                    BudgetAssignment.month_ord == month_ord,
                    BudgetAssignment.category_id == cat.id_,
                )
                .one_or_none()
            )
            if a is None:
                a = BudgetAssignment(
                    month_ord=month_ord,
                    category_id=cat.id_,
                    amount=amount,
                )
                s.add(a)
            else:
                a.amount = amount
        s.commit()

    table, _ = ctx_table(month=month)
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
    )


def overspending(uri: str) -> str | flask.Response:
    """GET & PUT /h/budgeting/c/<uri>/overspending.

    Args:
        uri: Category URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    month_str = args["month"]
    month = datetime.date.fromisoformat(month_str + "-01")
    month_ord = month.toordinal()

    with p.get_session() as s:
        t_cat: TransactionCategory | None
        t_cat = None if uri == "income" else web_utils.find(s, TransactionCategory, uri)
        categories, assignable, _ = BudgetAssignment.get_monthly_available(s, month)

        if flask.request.method == "PUT":
            if t_cat is None:
                available = assignable
            else:
                _, _, available = categories[t_cat.id_]
            source = flask.request.form["source"]
            if source == "income":
                source_id = None
                source_available = assignable
            else:
                source_id = TransactionCategory.uri_to_id(source)
                _, _, source_available = categories[source_id]
            to_move = min(source_available, -available)

            # Add assignment
            if t_cat is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == t_cat.id_,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=to_move,
                        category_id=t_cat.id_,
                    )
                    s.add(a)
                else:
                    a.amount += to_move

            if source_id is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == source_id,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=-to_move,
                        category_id=source_id,
                    )
                    s.add(a)
                elif a.amount == to_move:
                    s.delete(a)
                else:
                    a.amount -= to_move

            s.commit()
            return common.overlay_swap(event="update-budget")

        category_names = TransactionCategory.map_name(s)

        options: list[tuple[str, str, Decimal]] = [
            (
                TransactionCategory.id_to_uri(t_cat_id),
                category_names[t_cat_id],
                available,
            )
            for t_cat_id, (_, _, available) in categories.items()
            if available > 0
        ]
        if t_cat is None:
            available = assignable
        else:
            _, _, available = categories[t_cat.id_]
        options = sorted(options, key=lambda x: x[1])
        if assignable > 0:
            options.insert(0, ("income", "Assignable income", assignable))

        month_str = month.isoformat()[:7]
        category = {
            "uri": uri,
            "name": None if t_cat is None else t_cat.emoji_name,
            "available": available,
            "month": month_str,
            "options": options,
        }
    return flask.render_template(
        "budgeting/edit-overspending.jinja",
        category=category,
    )


def move(uri: str) -> str | flask.Response:
    """GET & PUT /h/budgeting/c/<uri>/move.

    Args:
        uri: Category URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    month_str = args["month"]
    month = datetime.date.fromisoformat(month_str + "-01")
    month_ord = month.toordinal()

    with p.get_session() as s:
        t_cat: TransactionCategory | None
        t_cat = None if uri == "income" else web_utils.find(s, TransactionCategory, uri)
        categories, assignable, _ = BudgetAssignment.get_monthly_available(s, month)

        if flask.request.method == "PUT":
            if t_cat is None:
                available = assignable
            else:
                _, _, available = categories[t_cat.id_]
            dest = flask.request.form["destination"]
            to_move = utils.parse_real(flask.request.form.get("amount"))
            if to_move is None:
                return common.error("Amount to move must not be blank")

            dest_id = None if dest == "income" else TransactionCategory.uri_to_id(dest)

            # Add assignment
            if t_cat is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == t_cat.id_,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=-to_move,
                        category_id=t_cat.id_,
                    )
                    s.add(a)
                elif a.amount == to_move:
                    s.delete(a)
                else:
                    a.amount -= to_move

            if dest_id is not None:
                a = (
                    s.query(BudgetAssignment)
                    .where(
                        BudgetAssignment.category_id == dest_id,
                        BudgetAssignment.month_ord == month_ord,
                    )
                    .one_or_none()
                )
                if a is None:
                    a = BudgetAssignment(
                        month_ord=month_ord,
                        amount=to_move,
                        category_id=dest_id,
                    )
                    s.add(a)
                else:
                    a.amount += to_move

            s.commit()
            return common.overlay_swap(event="update-budget")

        category_names = TransactionCategory.map_name(s)

        options: list[tuple[str, str, Decimal]] = [
            (
                TransactionCategory.id_to_uri(t_cat_id),
                category_names[t_cat_id],
                available,
            )
            for t_cat_id, (_, _, available) in categories.items()
            if (t_cat is None or t_cat_id != t_cat.id_) and t_cat_id in category_names
        ]
        if t_cat is None:
            available = assignable
        else:
            _, _, available = categories[t_cat.id_]
        options = sorted(options, key=lambda x: (x[2] >= 0, x[1]))
        if t_cat is not None:
            options.insert(0, ("income", "Assignable income", assignable))

        month_str = month.isoformat()[:7]
        category = {
            "uri": uri,
            "name": None if t_cat is None else t_cat.emoji_name,
            "available": available,
            "month": month_str,
            "options": options,
        }
    return flask.render_template(
        "budgeting/edit-move.jinja",
        category=category,
    )


def reorder() -> str:
    """GET & PUT /h/budgeting/reorder.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    # TODO(WattsUp): Same endpoint for new, rename, and delete?
    form = flask.request.form
    row_uris = form.getlist("row")
    groups = form.getlist("group")

    with p.get_session() as s:
        g_positions: dict[int, int] = {}
        t_cat_groups: dict[int, int | None] = {}
        t_cat_positions: dict[int, int | None] = {}

        i = 0
        i_group = 0
        last_group = None
        for t_cat_uri, g_uri in zip(row_uris, groups, strict=True):
            g_id = None if g_uri == "" else BudgetGroup.uri_to_id(g_uri)
            if g_uri != last_group:
                if g_id is not None:
                    g_positions[g_id] = i_group
                i = 0
                i_group += 1

            t_cat_id = TransactionCategory.uri_to_id(t_cat_uri)
            if g_id is None:
                t_cat_groups[t_cat_id] = None
                t_cat_positions[t_cat_id] = None
            else:
                t_cat_groups[t_cat_id] = g_id
                t_cat_positions[t_cat_id] = i

            i += 1
            last_group = g_uri

        # Set all to -index first so swapping can occur without unique violations
        s.query(BudgetGroup).update(
            {
                BudgetGroup.position: sql.case(
                    {g_id: -i for i, g_id in enumerate(g_positions)},
                    value=BudgetGroup.id_,
                ),
            },
        )
        # Set all to None first so swapping can occur without unique violations
        s.query(TransactionCategory).update(
            {
                TransactionCategory.budget_group_id: None,
                TransactionCategory.budget_position: None,
            },
        )

        s.query(BudgetGroup).update(
            {
                BudgetGroup.position: sql.case(
                    g_positions,
                    value=BudgetGroup.id_,
                ),
            },
        )
        s.query(TransactionCategory).update(
            {
                TransactionCategory.budget_group_id: sql.case(
                    t_cat_groups,
                    value=TransactionCategory.id_,
                ),
                TransactionCategory.budget_position: sql.case(
                    t_cat_positions,
                    value=TransactionCategory.id_,
                ),
            },
        )
        s.commit()

    table, _ = ctx_table()
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
    )


def group(uri: str) -> str:
    """PUT /h/budgeting/g/<path:uri>.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    # TODO(WattsUp): Same endpoint for new, rename, and delete?
    name = flask.request.form["name"]

    with p.get_session() as s:
        g = web_utils.find(s, BudgetGroup, uri)
        try:
            g.name = name
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

    table, _ = ctx_table()
    return flask.render_template(
        "budgeting/table.jinja",
        table=table,
        oob=True,
    )


ROUTES: Routes = {
    "/budgeting": (page, ["GET"]),
    "/h/budgeting/c/<path:uri>/assign": (assign, ["PUT"]),
    "/h/budgeting/c/<path:uri>/overspending": (overspending, ["GET", "PUT"]),
    "/h/budgeting/c/<path:uri>/move": (move, ["GET", "PUT"]),
    "/h/budgeting/reorder": (reorder, ["PUT"]),
    "/h/budgeting/g/<path:uri>": (group, ["PUT"]),
}
