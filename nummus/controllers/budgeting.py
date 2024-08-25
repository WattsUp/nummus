"""Budgeting controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
import sqlalchemy

from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    Account,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    YIELD_PER,
)
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
    end = utils.end_of_month(month)
    month_ord = month.toordinal()
    end_ord = end.toordinal()

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
        n_overspent = 0

        query = (
            s.query(BudgetAssignment)
            .with_entities(BudgetAssignment.category_id, BudgetAssignment.amount)
            .where(BudgetAssignment.month_ord == month_ord)
        )
        categories_assigned: dict[int, Decimal] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        query = (
            s.query(BudgetAssignment)
            .with_entities(sqlalchemy.func.sum(BudgetAssignment.amount))
            .where(BudgetAssignment.month_ord > month_ord)
        )
        future_assigned = query.scalar() or Decimal(0)

        groups: dict[str, GroupContext] = {}
        ungrouped: GroupContext = {
            "min_position": -1,
            "assigned": Decimal(0),
            "activity": Decimal(0),
            "available": Decimal(0),
            "categories": [],
        }

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.category_id,
                sqlalchemy.func.sum(TransactionSplit.amount),
            )
            .where(
                TransactionSplit.account_id.in_(accounts),
                TransactionSplit.date_ord >= month_ord,
                TransactionSplit.date_ord <= end_ord,
            )
            .group_by(TransactionSplit.category_id)
        )
        categories_activity: dict[int, Decimal] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]
        query = s.query(TransactionCategory)
        for t_cat in query.yield_per(YIELD_PER):
            activity = categories_activity.get(t_cat.id_, Decimal(0))
            assigned = categories_assigned.get(t_cat.id_, Decimal(0))
            # TODO (WattsUp): available includes leftovers from last month
            available = assigned + activity
            # Skip category if all numbers are 0 and not grouped
            if (
                t_cat.budget_group is None
                and activity == 0
                and assigned == 0
                and available == 0
            ):
                continue
            ending_balance += activity
            if t_cat.group == TransactionCategoryGroup.INCOME:
                continue
            total_available += available

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

        assignable = ending_balance - total_available - future_assigned

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
        "accounts": sorted(accounts.values()),
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
    amount = form.get("amount", type=utils.parse_real)
    if amount is None:
        msg = "Budget assignment must not be empty"
        raise ValueError(msg)

    with p.get_session() as s:
        cat = web_utils.find(s, TransactionCategory, uri)
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


ROUTES: Routes = {
    "/budgeting": (page, ["GET"]),
    "/h/budgeting/c/<path:uri>/assign": (assign, ["PUT"]),
}
