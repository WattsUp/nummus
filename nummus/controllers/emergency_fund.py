"""Emergency Savings controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import exceptions as exc
from nummus import portfolio, utils
from nummus.controllers import common
from nummus.models import Account
from nummus.models.base import YIELD_PER
from nummus.models.budget import BudgetAssignment
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


def page() -> flask.Response:
    """GET /emergency-fund.

    Returns:
        string HTML response
    """
    return common.page(
        "emergency-fund/page.jinja",
        "Emergency Fund",
        ctx=ctx_page(),
    )


def dashboard() -> str:
    """GET /h/dashboard/emergency-fund.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "emergency-fund/dashboard.jinja",
        ctx=ctx_page(),
    )


def ctx_page() -> dict[str, object]:
    """Get the context to build the emergency fund page.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    today = datetime.datetime.now().astimezone().date()
    today_ord = today.toordinal()
    start = utils.date_add_months(today, -6)
    start_ord = start.toordinal()
    n = today_ord - start_ord + 1

    with p.begin_session() as s:
        accounts: dict[int, str] = dict(
            s.query(Account)  # type: ignore[attr-defined]
            .with_entities(Account.id_, Account.name)
            .where(Account.budgeted)
            .all(),
        )

        try:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "emergency fund")
                .one()[0]
            )
        except exc.NoResultFound as e:  # pragma: no cover
            msg = "Category emergency fund not found"
            raise exc.ProtectedObjectNotFoundError(msg) from e

        balance = s.query(func.sum(BudgetAssignment.amount)).where(
            BudgetAssignment.category_id == t_cat_id,
            BudgetAssignment.month_ord <= start_ord,
        ).scalar() or Decimal(0)

        date_ord = start_ord
        balances: list[Decimal] = []

        query = (
            s.query(BudgetAssignment)
            .with_entities(BudgetAssignment.month_ord, BudgetAssignment.amount)
            .where(
                BudgetAssignment.category_id == t_cat_id,
                BudgetAssignment.month_ord > start_ord,
            )
            .order_by(BudgetAssignment.month_ord)
        )
        for b_ord, amount in query.all():
            while date_ord < b_ord:
                balances.append(balance)
                date_ord += 1
            balance += amount
        while date_ord <= today_ord:
            balances.append(balance)
            date_ord += 1

        n_smoothing = 15
        n_lower = utils.DAYS_IN_QUARTER
        n_upper = utils.DAYS_IN_QUARTER * 2

        categories: dict[int, tuple[str, str]] = {}
        categories_total: dict[int, Decimal] = {}

        daily = Decimal(0)
        dailys: list[Decimal] = []

        date_ord = start_ord - n_upper - n_smoothing

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
                TransactionSplit.date_ord >= date_ord,
            )
            .group_by(TransactionSplit.date_ord, TransactionSplit.category_id)
        )
        for t_ord, t_cat_id, amount in query.yield_per(YIELD_PER):
            while date_ord < t_ord:
                dailys.append(daily)
                date_ord += 1
                daily = Decimal(0)

            daily += amount

            if t_ord >= start_ord:
                categories_total[t_cat_id] += amount

        while date_ord <= today_ord:
            dailys.append(daily)
            date_ord += 1
            daily = Decimal(0)

        dates = utils.range_date(start_ord, today_ord)

    totals_lower = [
        -sum(dailys[i : i + n_lower]) for i in range(len(dailys) - n_lower + 1)
    ]
    totals_upper = [
        -sum(dailys[i : i + n_upper]) for i in range(len(dailys) - n_upper + 1)
    ]

    a_smoothing = 2 / Decimal(n_smoothing + 1)

    current = totals_lower[0]
    for i, x in enumerate(totals_lower):
        current = a_smoothing * x + (1 - a_smoothing) * current
        totals_lower[i] = current

    current = totals_upper[0]
    for i, x in enumerate(totals_upper):
        current = a_smoothing * x + (1 - a_smoothing) * current
        totals_upper[i] = current

    totals_lower = totals_lower[-n:]
    totals_upper = totals_upper[-n:]

    current = balances[-1]
    target_lower = totals_lower[-1]
    target_upper = totals_upper[-1]

    delta_lower = target_lower - current
    delta_upper = current - target_upper

    # Linearly interpret number of months
    if current < target_lower:
        months = None if target_lower == 0 else 3 * current / target_lower
    elif current > target_upper:
        months = None if target_upper == 0 else 6 * current / target_upper
    else:
        dx = target_upper - target_lower
        months = None if dx == 0 else 3 + (current - target_lower) / dx * 3

    class CategoryInfo(TypedDict):
        emoji_name: str
        name: str
        monthly: Decimal

    category_infos: list[CategoryInfo] = []
    for t_cat_id, (name, emoji_name) in categories.items():
        x_daily = -categories_total[t_cat_id] / n
        x_monthly = x_daily * utils.DAYS_IN_YEAR / 12
        category_infos.append(
            {
                "emoji_name": emoji_name,
                "name": name,
                "monthly": x_monthly,
            },
        )
    category_infos = sorted(
        category_infos,
        key=lambda item: (-round(item["monthly"], 2), item["name"]),
    )

    return {
        "chart": {
            "labels": [d.isoformat() for d in dates],
            "date_mode": "months",
            "balances": balances,
            "spending_lower": totals_lower,
            "spending_upper": totals_upper,
        },
        "current": current,
        "target_lower": target_lower,
        "target_upper": target_upper,
        "days": months and (months * utils.DAYS_IN_YEAR / utils.MONTHS_IN_YEAR),
        "delta_lower": delta_lower,
        "delta_upper": delta_upper,
        "categories": category_infos,
    }


ROUTES: Routes = {
    "/emergency-fund": (page, ["GET"]),
    "/h/dashboard/emergency-fund": (dashboard, ["GET"]),
}
