"""Cash Flow controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask
import sqlalchemy

from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    Account,
    AccountCategory,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)

if TYPE_CHECKING:
    from nummus import custom_types as t

DEFAULT_PERIOD = "90-days"


def ctx_chart() -> t.DictAny:
    """Get the context to build the net worth chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    category = args.get("category", None, type=AccountCategory)

    with p.get_session() as s:
        if start is None:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.asset_id.is_(None))
            query = query.with_entities(sqlalchemy.func.min(TransactionSplit.date_ord))
            start_ord = query.scalar()
            start = (
                datetime.date.fromordinal(start_ord)
                if start_ord
                else datetime.date(1970, 1, 1)
            )
        start_ord = start.toordinal()
        end_ord = end.toordinal()
        n = end_ord - start_ord + 1

        query = s.query(Account)
        if category is not None:
            query = query.where(Account.category == category)
        # Include account if not closed
        # Include account if most recent transaction is in period
        ids = [
            acct.id_
            for acct in query.all()
            if (not acct.closed or acct.updated_on_ord > start_ord)
        ]

        cash_flow = Account.get_cash_flow_all(s, start_ord, end_ord, ids=ids)
        income_daily: list[t.Real | None] = [None] * n
        expenses_daily: list[t.Real | None] = [None] * n

        query = s.query(TransactionCategory)
        query = query.with_entities(
            TransactionCategory.id_,
            TransactionCategory.group,
        )
        for cat_id, group in query.all():
            add_to: list[t.Real | None] | None = None
            if group == TransactionCategoryGroup.INCOME:
                add_to = income_daily
            elif group == TransactionCategoryGroup.EXPENSE:
                add_to = expenses_daily
            else:
                continue
            for i, amount in enumerate(cash_flow[cat_id]):
                v = add_to[i]
                add_to[i] = amount if v is None else v + amount

        income = utils.integrate(income_daily)
        expenses = utils.integrate(expenses_daily)
        total = [i + e for i, e in zip(income, expenses, strict=True)]

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "dates": [d.isoformat() for d in utils.range_date(start_ord, end_ord)],
            "total": total,
            "income": income,
            "expenses": expenses,
        },
        "category": category,
        "category_type": AccountCategory,
    }


def page() -> str:
    """GET /cash-flow.

    Returns:
        string HTML response
    """
    return common.page(
        "cash-flow/index-content.jinja",
        chart=ctx_chart(),
    )


def chart() -> str:
    """GET /h/cash-flow/chart.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "cash-flow/chart-data.jinja",
        chart=ctx_chart(),
        include_oob=True,
    )


def dashboard() -> str:
    """GET /h/dashboard/cash-flow.

    Returns:
        string HTML response
    """
    raise NotImplementedError
    return flask.render_template(
        "cash-flow/dashboard.jinja",
    )


ROUTES: t.Routes = {
    "/cash-flow": (page, ["GET"]),
    "/h/cash-flow/chart": (chart, ["GET"]),
    "/h/dashboard/cash-flow": (dashboard, ["GET"]),
}
