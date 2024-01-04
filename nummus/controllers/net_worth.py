"""Net worth controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask
import sqlalchemy

from nummus import portfolio, utils, web_utils
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
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    category = args.get("category", None, type=AccountCategory)
    no_defer = "no-defer" in args

    accounts: list[t.DictAny] = []

    with p.get_session() as s:
        if start is None:
            query = s.query(sqlalchemy.func.min(TransactionSplit.date_ord)).where(
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

        if n > web_utils.LIMIT_DEFER and not no_defer:
            return {
                "defer": True,
                "start": start,
                "end": end,
                "period": period,
                "category": category,
                "category_type": AccountCategory,
            }

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

        acct_values, _ = Account.get_value_all(s, start_ord, end_ord, ids=ids)

        total: t.Reals = [sum(item) for item in zip(*acct_values.values(), strict=True)]

        mapping = Account.map_name(s)

        for acct_id, values in acct_values.items():
            accounts.append(
                {
                    "name": mapping[acct_id],
                    "values": values,
                },
            )
        accounts = sorted(accounts, key=lambda item: -item["values"][-1])

        labels: t.Strings = []
        total_min: t.Reals | None = None
        total_max: t.Reals | None = None
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
    }


def page() -> str:
    """GET /net-worth.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    with p.get_session() as s:
        acct_values, _ = Account.get_value_all(s, today_ord, today_ord)
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

    with p.get_session() as s:
        end_ord = today_ord
        start = utils.date_add_months(today, -8)
        start_ord = start.toordinal()
        acct_values, _ = Account.get_value_all(s, start_ord, end_ord)

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


ROUTES: t.Routes = {
    "/net-worth": (page, ["GET"]),
    "/h/net-worth/chart": (chart, ["GET"]),
    "/h/dashboard/net-worth": (dashboard, ["GET"]),
}
