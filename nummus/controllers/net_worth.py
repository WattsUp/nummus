"""Net worth controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "90-days"


def ctx_chart() -> dict[str, object]:
    """Get the context to build the net worth chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
    category = args.get("category", None, type=AccountCategory)

    class AccountContext(TypedDict):
        """Type definition for Account context."""

        name: str
        values: list[Decimal]

    accounts: list[AccountContext] = []

    with p.begin_session() as s:
        if start is None:
            query = s.query(func.min(TransactionSplit.date_ord)).where(
                TransactionSplit.asset_id.is_(None),
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

        query = s.query(Account)
        if category is not None:
            query = query.where(Account.category == category)

        # Include account if not closed
        # Include account if most recent transaction is in period
        def include_account(acct: Account) -> bool:
            if not acct.closed:
                return True
            updated_on_ord = acct.updated_on_ord
            return updated_on_ord is not None and updated_on_ord > start_ord

        ids = [acct.id_ for acct in query.all() if include_account(acct)]

        acct_values, _, _ = Account.get_value_all(s, start_ord, end_ord, ids=ids)

        total: list[Decimal] = [
            Decimal(sum(item)) for item in zip(*acct_values.values(), strict=True)
        ]

        mapping = Account.map_name(s)

        sum_assets_end = Decimal(0)

        for acct_id, values in acct_values.items():
            accounts.append(
                {
                    "name": mapping[acct_id],
                    "values": values,
                },
            )
            sum_assets_end += max(0, values[-1])
        accounts = sorted(accounts, key=lambda item: -item["values"][-1])

        labels: list[str] = []
        total_min: list[Decimal] | None = None
        total_max: list[Decimal] | None = None
        date_mode: str | None = None

        if n > web_utils.LIMIT_DOWNSAMPLE:
            # Downsample to min/avg/max by month
            labels, total_min, total, total_max = utils.downsample(
                start_ord,
                end_ord,
                total,
            )
            date_mode = "years"

            for account in accounts:
                # Don't care about min/max cause stacked chart
                _, _, acct_values, _ = utils.downsample(
                    start_ord,
                    end_ord,
                    account["values"],
                )
                account["values"] = acct_values
        else:
            labels = [d.isoformat() for d in utils.range_date(start_ord, end_ord)]
            if n > web_utils.LIMIT_TICKS_MONTHS:
                date_mode = "months"
            elif n > web_utils.LIMIT_TICKS_WEEKS:
                date_mode = "weeks"
            else:
                date_mode = "days"

        assets = ctx_assets(s, start_ord, end_ord, sum_assets_end, ids)

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "labels": labels,
            "date_mode": date_mode,
            "values": total,
            "min": total_min,
            "max": total_max,
            "accounts": accounts,
        },
        "category": category,
        "category_type": AccountCategory,
        "assets": assets,
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


def page() -> flask.Response:
    """GET /net-worth.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    with p.begin_session() as s:
        acct_values, _, _ = Account.get_value_all(s, today_ord, today_ord)
        current = sum(item[0] for item in acct_values.values())
    return common.page(
        "net-worth/index-content.jinja",
        title="Net Worth | nummus",
        chart=ctx_chart(),
        current=current,
    )


def chart() -> str:
    """GET /h/net-worth/chart.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "net-worth/chart-data.jinja",
        chart=ctx_chart(),
        include_oob=True,
    )


def dashboard() -> str:
    """GET /h/dashboard/net-worth.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    with p.begin_session() as s:
        end_ord = today_ord
        start = utils.date_add_months(today, -8)
        start_ord = start.toordinal()
        acct_values, _, _ = Account.get_value_all(s, start_ord, end_ord)

        total = [sum(item) for item in zip(*acct_values.values(), strict=True)]

    chart = {
        "data": {
            "labels": [d.isoformat() for d in utils.range_date(start_ord, end_ord)],
            "date_mode": "months",
            "total": total,
        },
        "current": total[-1],
    }
    return flask.render_template(
        "net-worth/dashboard.jinja",
        chart=chart,
    )


ROUTES: Routes = {
    "/net-worth": (page, ["GET"]),
    "/h/net-worth/chart": (chart, ["GET"]),
    "/h/dashboard/net-worth": (dashboard, ["GET"]),
}
