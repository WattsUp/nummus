"""Emergency Savings controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import utils, web
from nummus.controllers import base
from nummus.models.budget import BudgetAssignment

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy import orm


class ChartContext(TypedDict):
    """Emergency fund chart context."""

    labels: list[str]
    date_mode: str
    balances: list[Decimal]
    spending_lower: list[Decimal]
    spending_upper: list[Decimal]


class CategoryInfo(TypedDict):
    """Category context."""

    emoji_name: str
    name: str
    monthly: Decimal


class EFundContext(TypedDict):
    """Emergency fund context."""

    chart: ChartContext
    current: Decimal
    target_lower: Decimal
    target_upper: Decimal
    days: Decimal | None
    delta_lower: Decimal
    delta_upper: Decimal
    categories: list[CategoryInfo]


def page() -> flask.Response:
    """GET /emergency-fund.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        return base.page(
            "emergency-fund/page.jinja",
            "Emergency fund",
            ctx=ctx_page(s, base.today_client()),
        )


def dashboard() -> str:
    """GET /h/dashboard/emergency-fund.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        return flask.render_template(
            "emergency-fund/dashboard.jinja",
            ctx=ctx_page(s, base.today_client()),
        )


def ctx_page(s: orm.Session, today: datetime.date) -> EFundContext:
    """Get the context to build the emergency fund page.

    Args:
        s: SQL session to use
        today: Today's date

    Returns:
        EFundContext

    """
    today_ord = today.toordinal()
    start = today - datetime.timedelta(days=utils.DAYS_IN_QUARTER * 2)
    start_ord = start.toordinal()
    n = today_ord - start_ord + 1

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
