"""Emergency Savings controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import portfolio, utils
from nummus.controllers import base
from nummus.models.budget import BudgetAssignment

if TYPE_CHECKING:
    from decimal import Decimal


def page() -> flask.Response:
    """GET /emergency-fund.

    Returns:
        string HTML response
    """
    return base.page(
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
        t_lowers, t_uppers, balances, categories, categories_total = (
            BudgetAssignment.get_emergency_fund(
                s,
                start_ord,
                today_ord,
                utils.DAYS_IN_QUARTER,
                utils.DAYS_IN_QUARTER * 2,
            )
        )
    dates = utils.range_date(start_ord, today_ord)

    current = balances[-1]
    target_lower = t_lowers[-1]
    target_upper = t_uppers[-1]

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
            "spending_lower": t_lowers,
            "spending_upper": t_uppers,
        },
        "current": current,
        "target_lower": target_lower,
        "target_upper": target_upper,
        "days": months and (months * utils.DAYS_IN_YEAR / utils.MONTHS_IN_YEAR),
        "delta_lower": delta_lower,
        "delta_upper": delta_upper,
        "categories": category_infos,
    }


ROUTES: base.Routes = {
    "/emergency-fund": (page, ["GET"]),
    "/h/dashboard/emergency-fund": (dashboard, ["GET"]),
}
