"""Net worth controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import utils, web
from nummus.controllers import base
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
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
        title="Net Worth",
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
        start, end = base.parse_period(base.DEFAULT_PERIOD, base.today_client())
        start = start or end
        start_ord = start.toordinal()
        end_ord = end.toordinal()
        acct_values, _, _ = Account.get_value_all(s, start_ord, end_ord)

        total = [sum(item) for item in zip(*acct_values.values(), strict=True)]

    ctx = {
        "chart": {
            "labels": [d.isoformat() for d in utils.range_date(start_ord, end_ord)],
            "mode": "months",
            "total": total,
        },
        "current": total[-1],
    }
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
    ]
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


def ctx_assets(
    s: orm.Session,
    start_ord: int,
    end_ord: int,
    total_value: Decimal,
    account_ids: list[int],
) -> dict[str, object]:
    """Get the context to build the assets list.

    Args:
        s: SQL session to use
        start_ord: First date ordinal to evaluate
        end_ord: Last date ordinal to evaluate (inclusive)
        total_value: Sum of all assets to compute value in cash
        account_ids: Limit results to specific Accounts by ID

    Returns:
        Dictionary HTML context
    """
    account_asset_qtys = Account.get_asset_qty_all(
        s,
        end_ord,
        end_ord,
        ids=account_ids,
    )
    asset_qtys: dict[int, Decimal] = {}
    for acct_assets in account_asset_qtys.values():
        for a_id, qtys in acct_assets.items():
            v = asset_qtys.get(a_id, Decimal(0))
            asset_qtys[a_id] = v + qtys[0]

    # Include assets that are currently held or had a change in qty
    query = s.query(TransactionSplit.asset_id).where(
        TransactionSplit.date_ord <= end_ord,
        TransactionSplit.date_ord >= start_ord,
        TransactionSplit.asset_id.is_not(None),
        TransactionSplit.account_id.in_(account_ids),
    )
    a_ids = {a_id for a_id, in query.distinct()}

    asset_qtys = {
        a_id: qty for a_id, qty in asset_qtys.items() if a_id in a_ids or qty != 0
    }
    a_ids = set(asset_qtys.keys())

    if len(a_ids) == 0:
        return {
            "assets": [
                {
                    "uri": None,
                    "category": AssetCategory.CASH,
                    "name": "Cash",
                    "end_qty": None,
                    "end_value": total_value,
                    "end_value_ratio": 1,
                    "profit": 0,
                },
            ],
            "end_value": total_value,
            "profit": 0,
        }

    end_prices = Asset.get_value_all(s, end_ord, end_ord, ids=a_ids)

    asset_profits = Account.get_profit_by_asset_all(
        s,
        start_ord,
        end_ord,
        ids=account_ids,
    )

    query = (
        s.query(Asset)
        .with_entities(
            Asset.id_,
            Asset.name,
            Asset.category,
        )
        .where(Asset.id_.in_(a_ids))
    )

    class AssetContext(TypedDict):
        """Type definition for Asset context."""

        uri: str | None
        category: AssetCategory
        name: str
        end_qty: Decimal | None
        end_value: Decimal
        end_value_ratio: Decimal
        profit: Decimal

    assets: list[AssetContext] = []
    cash = total_value
    total_profit = Decimal(0)
    for a_id, name, category in query.yield_per(YIELD_PER):
        end_qty = asset_qtys[a_id]
        end_value = end_qty * end_prices[a_id][0]
        profit = asset_profits[a_id]

        cash -= end_value
        total_profit += profit

        ctx_asset: AssetContext = {
            "uri": Asset.id_to_uri(a_id),
            "category": category,
            "name": name,
            "end_qty": end_qty,
            "end_value": end_value,
            "end_value_ratio": Decimal(0),
            "profit": profit,
        }
        assets.append(ctx_asset)

    # Add in cash too
    ctx_asset = {
        "uri": None,
        "category": AssetCategory.CASH,
        "name": "Cash",
        "end_qty": None,
        "end_value": cash,
        "end_value_ratio": Decimal(0),
        "profit": Decimal(0),
    }
    assets.append(ctx_asset)

    for item in assets:
        item["end_value_ratio"] = item["end_value"] / total_value

    assets = sorted(
        assets,
        key=lambda item: (
            -item["end_value"],
            -item["profit"],
            item["name"].lower(),
        ),
    )

    return {
        "assets": assets,
        "end_value": total_value,
        "profit": total_profit,
    }


ROUTES: Routes = {
    "/net-worth": (page, ["GET"]),
    "/h/net-worth/chart": (chart, ["GET"]),
    "/h/dashboard/net-worth": (dashboard, ["GET"]),
}
