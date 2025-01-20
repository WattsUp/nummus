"""Net worth controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import Account, AccountCategory, Asset, TransactionSplit
from nummus.models.asset import AssetCategory

if TYPE_CHECKING:
    from nummus.controllers.base import Routes

DEFAULT_PERIOD = "90-days"


def ctx_chart() -> dict[str, object]:
    """Get the context to build the performance chart.

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
    index = args.get("index", "S&P 500")

    class AccountContext(TypedDict):
        """Type definition for Account context."""

        name: str
        uri: str
        initial: Decimal
        end: Decimal
        profit: Decimal
        cash_flow: Decimal
        mwrr: Decimal

    accounts: list[AccountContext] = []

    with p.begin_session() as s:
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
        indices = {name: False for name, in query.all()}
        indices[index] = True
        index_description = (
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
            accounts.append(
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
        accounts = sorted(accounts, key=lambda item: -item["end"])

        labels: list[str] = []
        twrr_min: list[Decimal] | None = None
        twrr_max: list[Decimal] | None = None
        index_twrr_min: list[Decimal] | None = None
        index_twrr_max: list[Decimal] | None = None
        date_mode: str | None = None

        if n > web_utils.LIMIT_DOWNSAMPLE:
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
            if n > web_utils.LIMIT_TICKS_MONTHS:
                date_mode = "months"
            elif n > web_utils.LIMIT_TICKS_WEEKS:
                date_mode = "weeks"
            else:
                date_mode = "days"

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "labels": labels,
            "date_mode": date_mode,
            "values": twrr,
            "min": twrr_min,
            "max": twrr_max,
            "index": index_twrr,
            "index_min": index_twrr_min,
            "index_max": index_twrr_max,
        },
        "accounts": {
            "initial": total[0],
            "end": total[-1],
            "cash_flow": sum_cash_flow,
            "profit": total_profit[-1],
            "mwrr": mwrr,
            "accounts": accounts,
        },
        "indices": indices,
        "index_description": index_description,
    }


def page() -> flask.Response:
    """GET /performance.

    Returns:
        string HTML response
    """
    return common.page(
        "performance/index-content.jinja",
        title="Performance | nummus",
        chart=ctx_chart(),
    )


def chart() -> str:
    """GET /h/performance/chart.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "performance/chart-data.jinja",
        chart=ctx_chart(),
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


ROUTES: Routes = {
    "/performance": (page, ["GET"]),
    "/h/performance/chart": (chart, ["GET"]),
    "/h/dashboard/performance": (dashboard, ["GET"]),
}
