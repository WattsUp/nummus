"""Performance controllers."""

from __future__ import annotations

import datetime
import math
import operator
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import sql, utils, web
from nummus.controllers import base
from nummus.models.account import Account, AccountCategory
from nummus.models.asset import (
    Asset,
    AssetCategory,
)
from nummus.models.config import Config
from nummus.models.currency import (
    Currency,
    CURRENCY_FORMATS,
)
from nummus.models.transaction import TransactionSplit
from nummus.sql import yield_

if TYPE_CHECKING:

    from nummus.models.currency import Currency, CurrencyFormat

_DEFAULT_INDEX = "S&P 500"


class AccountContext(TypedDict):
    """Type definition for Account context."""

    name: str
    uri: str
    initial: Decimal
    end: Decimal
    pnl: Decimal
    cash_flow: Decimal
    mwrr: Decimal | None


class AccountsContext(TypedDict):
    """Type definition for Accounts context."""

    initial: Decimal
    end: Decimal
    cash_flow: Decimal
    pnl: Decimal
    mwrr: Decimal | None
    accounts: list[AccountContext]
    options: list[base.NamePairState]
    currency_format: CurrencyFormat


class ChartData(base.ChartData):
    """Type definition for chart data context."""

    index: list[Decimal]
    index_name: str
    index_min: list[Decimal] | None
    index_max: list[Decimal] | None
    mwrr: list[Decimal] | None
    currency_format: dict[str, object]


class Context(TypedDict):
    """Type definition for chart context."""

    start: datetime.date
    end: datetime.date
    period: str
    period_options: dict[str, str]
    chart: ChartData
    accounts: AccountsContext
    index: str
    indices: list[str]
    index_description: str | None


def page() -> flask.Response:
    """GET /performance.

    Returns:
        string HTML response

    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session():
        ctx = ctx_chart(
            base.today_client(),
            args.get("period", base.DEFAULT_PERIOD),
            args.get("index", _DEFAULT_INDEX),
            {Account.uri_to_id(uri) for uri in args.getlist("exclude")},
        )
    return base.page(
        "performance/page.jinja",
        title="Performance",
        ctx=ctx,
    )


def chart() -> flask.Response:
    """GET /h/performance/chart.

    Returns:
        string HTML response

    """
    args = flask.request.args
    period = args.get("period", base.DEFAULT_PERIOD)
    index = args.get("index", _DEFAULT_INDEX)
    excluded_accounts = args.getlist("exclude")
    p = web.portfolio
    with p.begin_session():
        ctx = ctx_chart(
            base.today_client(),
            period,
            index,
            {Account.uri_to_id(uri) for uri in excluded_accounts},
        )
    html = flask.render_template(
        "performance/chart-data.jinja",
        ctx=ctx,
        include_oob=True,
    )
    response = flask.make_response(html)
    response.headers["HX-Push-Url"] = flask.url_for(
        "performance.page",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        period=period,
        index=index,
        exclude=excluded_accounts,
    )
    return response


def dashboard() -> str:
    """GET /h/dashboard/performance.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session():
        acct_ids = Account.ids(AccountCategory.INVESTMENT)
        end = base.today_client()
        start = end - datetime.timedelta(days=90)
        start_ord = start.toordinal()
        end_ord = end.toordinal()
        n = end_ord - start_ord + 1

        indices: dict[str, Decimal] = {}
        query = (
            Asset.query(Asset.name)
            .where(Asset.category == AssetCategory.INDEX)
            .order_by(Asset.name)
        )
        for (name,) in yield_(query):
            twrr = Asset.index_twrr(name, start_ord, end_ord)
            indices[name] = twrr[-1]

        acct_values, acct_profits, _ = Account.get_value_all(
            start_ord,
            end_ord,
            ids=acct_ids,
        )

        total: list[Decimal] = [
            Decimal(sum(item)) for item in zip(*acct_values.values(), strict=True)
        ] or [Decimal(0)] * n
        total_profit: list[Decimal] = [
            Decimal(sum(item)) for item in zip(*acct_profits.values(), strict=True)
        ] or [Decimal(0)] * n
        twrr = utils.twrr(total, total_profit)

        ctx = {
            "pnl": total_profit[-1],
            "twrr": twrr[-1],
            "indices": indices,
            "currency_format": CURRENCY_FORMATS[Config.base_currency()],
        }
    return flask.render_template(
        "performance/dashboard.jinja",
        ctx=ctx,
    )


def ctx_chart(
    today: datetime.date,
    period: str,
    index: str,
    excluded_accounts: set[int],
) -> Context:
    """Get the context to build the performance chart.

    Args:
        today: Today's date
        period: Selected chart period
        index: Selected index to compare against
        excluded_accounts: Selected accounts to excluded

    Returns:
        Dictionary HTML context

    """
    start, end = base.parse_period(period, today)

    ctx_accounts: list[AccountContext] = []

    acct_ids = Account.ids(AccountCategory.INVESTMENT)
    if start is None:
        query = TransactionSplit.query(func.min(TransactionSplit.date_ord)).where(
            TransactionSplit.asset_id.is_(None),
            TransactionSplit.account_id.in_(acct_ids),
        )
        start_ord = sql.scalar(query)
        start = datetime.date.fromordinal(start_ord) if start_ord else end
    start_ord = start.toordinal()
    end_ord = end.toordinal()
    n = end_ord - start_ord + 1

    query = (
        Asset.query(Asset.name)
        .where(Asset.category == AssetCategory.INDEX)
        .order_by(Asset.name)
    )
    indices: list[str] = list(sql.col0(query))
    index_description: str | None = sql.scalar(
        Asset.query(Asset.description).where(Asset.name == index),
    )

    query = Account.query().where(Account.id_.in_(acct_ids))
    mapping: dict[int, str] = {}
    currencies: dict[int, Currency] = {}
    acct_ids.clear()
    account_options: list[base.NamePairState] = []
    for acct in sql.yield_(query):
        if acct.do_include(start_ord):
            excluded = acct.id_ in excluded_accounts
            account_options.append(
                base.NamePairState(acct.uri, acct.name, state=excluded),
            )
            if not excluded:
                mapping[acct.id_] = acct.name
                currencies[acct.id_] = acct.currency
                acct_ids.add(acct.id_)

    base_currency = Config.base_currency()
    forex = Asset.get_forex(
        start_ord,
        end_ord,
        base_currency,
        set(currencies.values()),
    )

    acct_values, acct_profits, _ = Account.get_value_all(
        start_ord,
        end_ord,
        ids=acct_ids,
        forex=forex,
    )

    total: list[Decimal] = [
        Decimal(sum(item)) for item in zip(*acct_values.values(), strict=True)
    ] or [Decimal(0)] * n
    total_profit: list[Decimal] = [
        Decimal(sum(item)) for item in zip(*acct_profits.values(), strict=True)
    ] or [Decimal(0)] * n
    twrr = utils.twrr(total, total_profit)
    mwrr = utils.mwrr(total, total_profit)

    index_twrr = Asset.index_twrr(index, start_ord, end_ord)

    sum_cash_flow = Decimal(0)

    for acct_id, values in acct_values.items():
        profits = acct_profits[acct_id]

        v_initial = values[0] - profits[0]
        v_end = values[-1]
        profit = profits[-1]
        cash_flow = (v_end - v_initial) - profit
        ctx_accounts.append(
            {
                "name": mapping[acct_id],
                "uri": Account.id_to_uri(acct_id),
                "initial": v_initial,
                "end": v_end,
                "pnl": profit,
                "cash_flow": cash_flow,
                "mwrr": utils.mwrr(values, profits),
            },
        )
        sum_cash_flow += cash_flow
    ctx_accounts = sorted(ctx_accounts, key=lambda item: -item["end"])

    if mwrr is None:
        mwrr_interpolation = [Decimal()] * len(twrr)
    else:
        r = Decimal(math.log(mwrr + 1)) / utils.DAYS_IN_YEAR
        mwrr_interpolation = [Decimal(math.exp(i * r) - 1) for i in range(len(twrr))]
    data_twrr, data_index, data_mwrr = base.chart_data(
        start_ord,
        end_ord,
        (twrr, index_twrr, mwrr_interpolation),
    )

    cf = CURRENCY_FORMATS[base_currency]
    chart: ChartData = {
        **data_twrr,
        "index": data_index["avg"],
        "index_name": index,
        "index_min": data_index["min"],
        "index_max": data_index["max"],
        "mwrr": None if mwrr is None else data_mwrr["avg"],
        "currency_format": cf._asdict(),
    }

    accounts: AccountsContext = {
        "initial": total[0],
        "end": total[-1],
        "cash_flow": sum_cash_flow,
        "pnl": total_profit[-1],
        "mwrr": mwrr,
        "accounts": ctx_accounts,
        "options": sorted(account_options, key=operator.itemgetter(0)),
        "currency_format": cf,
    }

    return {
        "start": start,
        "end": end,
        "period": period,
        "period_options": base.PERIOD_OPTIONS,
        "chart": chart,
        "accounts": accounts,
        "index": index,
        "indices": indices,
        "index_description": index_description,
    }


ROUTES: base.Routes = {
    "/performance": (page, ["GET"]),
    "/h/performance/chart": (chart, ["GET"]),
    "/h/dashboard/performance": (dashboard, ["GET"]),
}
