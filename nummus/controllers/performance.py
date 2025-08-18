"""Performance controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import portfolio, utils, web
from nummus.controllers import base, common
from nummus.models import Account, AccountCategory, Asset, TransactionSplit
from nummus.models.asset import AssetCategory

_DEFAULT_PERIOD = "6m"
_DEFAULT_INDEX = "S&P 500"


class AccountContext(TypedDict):
    """Type definition for Account context."""

    name: str
    uri: str
    initial: Decimal
    end: Decimal
    profit: Decimal
    cash_flow: Decimal
    mwrr: Decimal | None


class AccountsContext(TypedDict):
    """Type definition for Accounts context."""

    initial: Decimal
    end: Decimal
    cash_flow: Decimal
    profit: Decimal
    mwrr: Decimal | None
    accounts: list[AccountContext]


class ChartData(TypedDict):
    """Type definition for chart data context."""

    labels: list[str]
    date_mode: str
    values: list[Decimal]
    min: list[Decimal] | None
    max: list[Decimal] | None
    index: list[Decimal]
    index_name: str
    index_min: list[Decimal] | None
    index_max: list[Decimal] | None


class ChartContext(TypedDict):
    """Type definition for chart context."""

    start: datetime.date
    end: datetime.date
    period: str
    period_options: dict[str, str]
    data: ChartData
    accounts: AccountsContext
    indices: dict[str, bool]
    index_description: str | None


def page() -> flask.Response:
    """GET /performance.

    Returns:
        string HTML response
    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        ctx = ctx_chart(
            s,
            base.today_client(),
            args.get("period", _DEFAULT_PERIOD),
            args.get("index", _DEFAULT_INDEX),
        )
    return base.page(
        "performance/page.jinja",
        title="Performance",
        chart=ctx,
    )


def chart() -> str:
    """GET /h/performance/chart.

    Returns:
        string HTML response
    """
    args = flask.request.args
    p = web.portfolio
    with p.begin_session() as s:
        ctx = ctx_chart(
            s,
            base.today_client(),
            args.get("period", _DEFAULT_PERIOD),
            args.get("index", _DEFAULT_INDEX),
        )
    return flask.render_template(
        "performance/chart-data.jinja",
        chart=ctx,
        include_oob=True,
    )


def dashboard() -> str:
    """GET /h/dashboard/performance.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        acct_ids = Account.ids(s, AccountCategory.INVESTMENT)
        end = datetime.date.today()
        start = end - datetime.timedelta(days=90)
        start_ord = start.toordinal()
        end_ord = end.toordinal()
        n = end_ord - start_ord + 1

        indices: dict[str, Decimal] = {}
        query = s.query(Asset.name).where(Asset.category == AssetCategory.INDEX)
        for (name,) in query.all():
            twrr = Asset.index_twrr(s, name, start_ord, end_ord)
            indices[name] = twrr[-1]

        acct_values, acct_profits, _ = Account.get_value_all(
            s,
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
            "profit": total_profit[-1],
            "twrr": twrr[-1],
            "indices": indices,
        }
    return flask.render_template(
        "performance/dashboard.jinja",
        data=ctx,
    )


def ctx_chart(
    s: orm.Session,
    today: datetime.date,
    period: str,
    index: str,
) -> ChartContext:
    """Get the context to build the performance chart.

    Args:
        s: SQL session to use
        today: Today's date
        period: Selected chart period
        index: Selected index to compare against

    Returns:
        Dictionary HTML context
    """
    start, end = base.parse_period(period, today)

    ctx_accounts: list[AccountContext] = []

    acct_ids = Account.ids(s, AccountCategory.INVESTMENT)
    if start is None:
        query = s.query(func.min(TransactionSplit.date_ord)).where(
            TransactionSplit.asset_id.is_(None),
            TransactionSplit.account_id.in_(acct_ids),
        )
        start_ord = query.scalar()
        start = (
            datetime.date.fromordinal(start_ord)
            if start_ord
            else datetime.date(1970, 1, 1)
        )
    start_ord = start.toordinal()
    end_ord = end.toordinal()
    n = end_ord - start_ord + 1

    query = s.query(Asset.name).where(Asset.category == AssetCategory.INDEX)
    indices: dict[str, bool] = {name: False for (name,) in query.all()}
    indices[index] = True
    index_description: str | None = (
        s.query(Asset.description).where(Asset.name == index).scalar()
    )

    query = s.query(Account).where(Account.id_.in_(acct_ids))

    # Include account if not closed
    # Include account if most recent transaction is in period
    def include_account(acct: Account) -> bool:
        if not acct.closed:
            return True
        updated_on_ord = acct.updated_on_ord
        return updated_on_ord is not None and updated_on_ord > start_ord

    acct_ids = [acct.id_ for acct in query.all() if include_account(acct)]

    acct_values, acct_profits, _ = Account.get_value_all(
        s,
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
    mwrr = utils.mwrr(total, total_profit)

    index_twrr = Asset.index_twrr(s, index, start_ord, end_ord)

    mapping = Account.map_name(s)

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
                "profit": profit,
                "cash_flow": cash_flow,
                "mwrr": utils.mwrr(values, profits),
            },
        )
        sum_cash_flow += cash_flow
    ctx_accounts = sorted(ctx_accounts, key=lambda item: -item["end"])

    labels: list[str] = []
    twrr_min: list[Decimal] | None = None
    twrr_max: list[Decimal] | None = None
    index_twrr_min: list[Decimal] | None = None
    index_twrr_max: list[Decimal] | None = None
    date_mode: str | None = None

    if n > base.LIMIT_DOWNSAMPLE:
        # Downsample to min/avg/max by month
        labels, twrr_min, twrr, twrr_max = utils.downsample(
            start_ord,
            end_ord,
            twrr,
        )
        _, index_twrr_min, index_twrr, index_twrr_max = utils.downsample(
            start_ord,
            end_ord,
            index_twrr,
        )
        date_mode = "years"
    else:
        labels = [d.isoformat() for d in utils.range_date(start_ord, end_ord)]
        if n > base.LIMIT_TICKS_MONTHS:
            date_mode = "months"
        elif n > base.LIMIT_TICKS_WEEKS:
            date_mode = "weeks"
        else:
            date_mode = "days"

    data: ChartData = {
        "labels": labels,
        "date_mode": date_mode,
        "values": twrr,
        "min": twrr_min,
        "max": twrr_max,
        "index": index_twrr,
        "index_name": index,
        "index_min": index_twrr_min,
        "index_max": index_twrr_max,
    }

    accounts: AccountsContext = {
        "initial": total[0],
        "end": total[-1],
        "cash_flow": sum_cash_flow,
        "profit": total_profit[-1],
        "mwrr": mwrr,
        "accounts": ctx_accounts,
    }

    return {
        "start": start,
        "end": end,
        "period": period,
        "period_options": base.PERIOD_OPTIONS,
        "data": data,
        "accounts": accounts,
        "indices": indices,
        "index_description": index_description,
    }


ROUTES: base.Routes = {
    "/performance": (page, ["GET"]),
    "/h/performance/chart": (chart, ["GET"]),
    "/h/dashboard/performance": (dashboard, ["GET"]),
}
