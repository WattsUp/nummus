"""Net worth controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import web
from nummus.controllers import base
from nummus.models import (
    Account,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.controllers.base import Routes


class AccountContext(TypedDict):
    """Type definition for Account context."""

    name: str
    uri: str
    min: list[Decimal] | None
    avg: list[Decimal]
    max: list[Decimal] | None


class Context(TypedDict):
    """Type definition for chart context."""

    start: datetime.date
    end: datetime.date
    period: str
    period_options: dict[str, str]
    chart: base.ChartData
    accounts: list[AccountContext]
    net_worth: Decimal
    assets: Decimal
    liabilities: Decimal
    assets_w: Decimal
    liabilities_w: Decimal


def page() -> flask.Response:
    """GET /net-worth.

    Returns:
        string HTML response

    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        ctx = ctx_chart(
            s,
            base.today_client(),
            args.get("period", base.DEFAULT_PERIOD),
        )
    return base.page(
        "net-worth/page.jinja",
        title="Net worth",
        ctx=ctx,
    )


def chart() -> flask.Response:
    """GET /h/net-worth/chart.

    Returns:
        string HTML response

    """
    args = flask.request.args
    period = args.get("period", base.DEFAULT_PERIOD)
    p = web.portfolio
    with p.begin_session() as s:
        ctx = ctx_chart(s, base.today_client(), period)
    html = flask.render_template(
        "net-worth/chart-data.jinja",
        ctx=ctx,
        include_oob=True,
    )
    response = flask.make_response(html)
    response.headers["HX-Push-Url"] = flask.url_for(
        "net_worth.page",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        period=period,
    )
    return response


def dashboard() -> str:
    """GET /h/dashboard/net-worth.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        ctx = ctx_chart(
            s,
            base.today_client(),
            base.DEFAULT_PERIOD,
        )
    return flask.render_template(
        "net-worth/dashboard.jinja",
        ctx=ctx,
    )


def ctx_chart(
    s: orm.Session,
    today: datetime.date,
    period: str,
) -> Context:
    """Get the context to build the net worth chart.

    Args:
        s: SQL session to use
        today: Today's date
        period: Selected chart period

    Returns:
        Dictionary HTML context

    """
    start, end = base.parse_period(period, today)

    if start is None:
        query = s.query(func.min(TransactionSplit.date_ord)).where(
            TransactionSplit.asset_id.is_(None),
        )
        start_ord = query.scalar()
        start = datetime.date.fromordinal(start_ord) if start_ord else end
    start_ord = start.toordinal()
    end_ord = end.toordinal()

    query = s.query(Account)
    acct_ids = [acct.id_ for acct in query.all() if acct.do_include(start_ord)]

    acct_values, _, _ = Account.get_value_all(
        s,
        start_ord,
        end_ord,
        ids=acct_ids,
    )

    total: list[Decimal] = [
        Decimal(sum(item)) for item in zip(*acct_values.values(), strict=True)
    ] or [Decimal()] * (end_ord - start_ord + 1)
    data_tuple = base.chart_data(start_ord, end_ord, (total, *acct_values.values()))

    mapping = Account.map_name(s)

    ctx_accounts: list[AccountContext] = [
        {
            "name": mapping[acct_id],
            "uri": Account.id_to_uri(acct_id),
            "min": data_tuple[i + 1]["min"],
            "avg": data_tuple[i + 1]["avg"],
            "max": data_tuple[i + 1]["max"],
        }
        for i, acct_id in enumerate(acct_values)
    ]
    ctx_accounts = sorted(ctx_accounts, key=lambda item: -item["avg"][-1])

    assets = Decimal()
    liabilities = Decimal()
    for values in acct_values.values():
        v = values[-1]
        if v > 0:
            assets += v
        else:
            liabilities += v

    bar_total = assets - liabilities
    if bar_total == 0:
        asset_width = Decimal()
        liabilities_width = Decimal()
    else:
        asset_width = round(assets / (assets - liabilities) * 100, 2)
        liabilities_width = 100 - asset_width

    return {
        "start": start,
        "end": end,
        "period": period,
        "period_options": base.PERIOD_OPTIONS,
        "chart": data_tuple[0],
        "accounts": ctx_accounts,
        "net_worth": assets + liabilities,
        "assets": assets,
        "liabilities": liabilities,
        "assets_w": asset_width,
        "liabilities_w": liabilities_width,
    }


ROUTES: Routes = {
    "/net-worth": (page, ["GET"]),
    "/h/net-worth/chart": (chart, ["GET"]),
    "/h/dashboard/net-worth": (dashboard, ["GET"]),
}
