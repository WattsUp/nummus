"""Budgeting controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import TransactionCategory, TransactionCategoryGroup, YIELD_PER
from nummus.models.budget import BudgetAssignment

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

    class GroupContext(TypedDict):
        """Type definition for budget group context."""

        min_position: int
        categories: list[CategoryContext]
        assigned: Decimal
        activity: Decimal
        available: Decimal

    with p.get_session() as s:
        categories, assignable, future_assigned = (
            BudgetAssignment.get_monthly_available(s, month)
        )
        n_overspent = 0

        groups: dict[str, GroupContext] = {}
        ungrouped: GroupContext = {
            "min_position": -1,
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
                t_cat.budget_group is None
                and activity == 0
                and assigned == 0
                and available == 0
            ):
                continue
            if t_cat.group == TransactionCategoryGroup.INCOME:
                continue

            if available < 0:
                n_overspent += 1

            cat_ctx: CategoryContext = {
                "position": t_cat.budget_position,
                "uri": t_cat.uri,
                "name": t_cat.name,
                "emoji_name": t_cat.emoji_name,
                "assigned": assigned,
                "activity": activity,
                "available": available,
            }
            if t_cat.budget_group is None:
                group = ungrouped
            else:
                if t_cat.budget_group not in groups:
                    groups[t_cat.budget_group] = {
                        "min_position": t_cat.budget_position or 0,
                        "assigned": Decimal(0),
                        "activity": Decimal(0),
                        "available": Decimal(0),
                        "categories": [],
                    }
                group = groups[t_cat.budget_group]

                # Calculate the minimum position caring for None
                group["min_position"] = min(
                    group["min_position"] or 0,
                    t_cat.budget_position or 0,
                )
            group["assigned"] += assigned
            group["activity"] += activity
            group["available"] += available
            group["categories"].append(cat_ctx)

        groups_list = sorted(groups.items(), key=lambda item: item[1]["min_position"])
        if ungrouped["categories"]:
            groups_list.append(("Ungrouped", ungrouped))

        for _, group in groups_list:
            group["categories"] = sorted(
                group["categories"],
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

    form = flask.request.form
    month = datetime.date.fromisoformat(form["month"] + "-01")
    month_ord = month.toordinal()
    amount = form.get("amount", type=utils.parse_real) or Decimal(0)

    with p.get_session() as s:
        cat: TransactionCategory = web_utils.find(s, TransactionCategory, uri)  # type: ignore[attr-defined]
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
        t_cat: TransactionCategory = web_utils.find(s, TransactionCategory, uri)  # type: ignore[attr-defined]
        categories, assignable, _ = BudgetAssignment.get_monthly_available(s, month)

        if flask.request.method == "PUT":
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
        _, _, available = categories[t_cat.id_]
        options = sorted(options, key=lambda x: x[1])
        if assignable > 0:
            options.insert(0, ("income", "Assignable income", assignable))

        month_str = month.isoformat()[:7]
        category = {
            "uri": uri,
            "name": t_cat.emoji_name,
            "available": available,
            "month": month_str,
            "options": options,
        }
    return flask.render_template(
        "budgeting/edit-overspending.jinja",
        category=category,
    )


ROUTES: Routes = {
    "/budgeting": (page, ["GET"]),
    "/h/budgeting/c/<path:uri>/assign": (assign, ["PUT"]),
    "/h/budgeting/c/<path:uri>/overspending": (overspending, ["GET", "PUT"]),
}
