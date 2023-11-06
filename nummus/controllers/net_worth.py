"""Net worth controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask
import sqlalchemy.exc

from nummus import portfolio, web_utils
from nummus.controllers import common
from nummus.models import Account, AccountCategory, TransactionSplit

if TYPE_CHECKING:
    from nummus import custom_types as t

DEFAULT_PERIOD = "90-days"


def ctx_chart() -> t.DictAny:
    """Get the context to build the net worth chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    category = args.get("category", None, type=AccountCategory)

    accounts: list[t.DictAny] = []

    with p.get_session() as s:
        # TODO(WatsUp): Net worth, period=all is too slow
        if start is None:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.asset_id.is_(None))
            query = query.with_entities(sqlalchemy.func.min(TransactionSplit.date))
            start = query.scalar() or datetime.date(1970, 1, 1)

        query = s.query(Account)
        if category is not None:
            query = query.where(Account.category == category)
        # Include account if not closed
        # Include account if most recent transaction is in period
        ids = [
            acct.id_
            for acct in query.all()
            if (not acct.closed or acct.updated_on > start)
        ]

        dates, acct_values = Account.get_value_all(s, start, end, ids=ids)

        total = [sum(item) for item in zip(*acct_values.values(), strict=True)]

        mapping = Account.map_name(s)

        for acct_id, values in acct_values.items():
            accounts.append(
                {
                    "name": mapping[acct_id],
                    "values": values,
                },
            )

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "dates": [d.isoformat() for d in dates],
            "total": total,
            "accounts": accounts,
        },
        "category": category,
        "category_type": AccountCategory,
    }


def page() -> str:
    """GET /net-worth.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio
    today = datetime.date.today()

    with p.get_session() as s:
        _, acct_values = Account.get_value_all(s, today, today)
        current = sum(item[0] for item in acct_values.values())
    return common.page(
        "net-worth/index-content.jinja",
        chart=ctx_chart(),
        current=current,
    )


def chart() -> str:
    """GET /h/net-worth/chart.

    Returns:
        string HTML response
    """
    return common.page(
        "net-worth/chart-data.jinja",
        chart=ctx_chart(),
        include_oob=True,
    )


ROUTES: t.Routes = {
    "/net-worth": (page, ["GET"]),
    "/h/net-worth/chart": (chart, ["GET"]),
}
