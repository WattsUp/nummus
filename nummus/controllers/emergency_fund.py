"""Emergency Savings controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
import sqlalchemy

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


def ctx_page() -> dict[str, object]:
    """Get the context to build the emergency fund page.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    today = datetime.date.today()
    today_ord = today.toordinal()
    start = utils.date_add_months(today, -6)
    start_ord = start.toordinal()
    n = today_ord - start_ord + 1

    with p.get_session() as s:
        accounts: dict[int, str] = dict(
            s.query(Account)  # type: ignore[attr-defined]
            .with_entities(Account.id_, Account.name)
            .where(Account.budgeted)
            .all(),
        )

        try:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Emergency Fund")
                .one()[0]
            )
        except exc.NoResultFound as e:  # pragma: no cover
            msg = "Category Uncategorized not found"
            raise exc.ProtectedObjectNotFoundError(msg) from e

        balance = s.query(sqlalchemy.func.sum(BudgetAssignment.amount)).where(
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
        while date_ord < today_ord:
            balances.append(balance)
            date_ord += 1

        n_smoothing = 15
        n_lower = 91
        n_upper = 182

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
                TransactionCategory.emoji,
            )
            .where(TransactionCategory.essential)
        )
        for t_cat_id, name, emoji in query.all():
            categories[t_cat_id] = (name, f"{emoji} {name}" if emoji else name)
            categories_total[t_cat_id] = Decimal(0)

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.category_id,
                sqlalchemy.func.sum(TransactionSplit.amount),
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

        while date_ord < start_ord:
            dailys.append(daily)
            date_ord += 1
            daily = Decimal(0)

        dates = utils.range_date(start_ord, today_ord)

    totals_lower = [-sum(dailys[i : i + n_lower]) for i in range(len(dailys) - n_lower)]
    totals_upper = [-sum(dailys[i : i + n_upper]) for i in range(len(dailys) - n_upper)]

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
        months = 3 * current / target_lower
    elif current > target_upper:
        months = 6 * current / target_upper
    else:
        months = 3 + (current - target_lower) / (target_upper - target_lower) * 3

    class CategoryInfo(TypedDict):
        emoji_name: str
        name: str
        monthly: Decimal
        lower: Decimal
        upper: Decimal

    category_infos: list[CategoryInfo] = []
    for t_cat_id, (name, emoji_name) in categories.items():
        x_daily = -categories_total[t_cat_id] / n
        x_lower = x_daily * n_lower
        x_upper = x_daily * n_upper
        x_monthly = x_upper / 6
        category_infos.append(
            {
                "emoji_name": emoji_name,
                "name": name,
                "monthly": x_monthly,
                "lower": x_lower,
                "upper": x_upper,
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
        "months": months,
        "delta_lower": delta_lower,
        "delta_upper": delta_upper,
        "categories": category_infos,
    }


def page() -> str:
    """GET /emergency-fund.

    Returns:
        string HTML response
    """
    return common.page(
        "emergency-fund/index-content.jinja",
        title="Emergency Fund | nummus",
        e_fund=ctx_page(),
    )


def dashboard() -> str:
    """GET /h/dashboard/emergency-fund.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "emergency-fund/dashboard.jinja",
        e_fund=ctx_page(),
    )


ROUTES: Routes = {
    "/emergency-fund": (page, ["GET"]),
    "/h/dashboard/emergency-fund": (dashboard, ["GET"]),
}
