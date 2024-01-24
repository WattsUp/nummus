"""Account controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import flask
import sqlalchemy
from sqlalchemy import orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common, transactions
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus import custom_types as t

DEFAULT_PERIOD = "90-days"
PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


def edit(uri: str) -> str | flask.Response:
    """GET & POST /h/accounts/a/<uri>/edit.

    Args:
        uri: Account URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    with p.get_session() as s:
        acct: Account = web_utils.find(s, Account, uri)  # type: ignore[attr-defined]

        values, _, _ = acct.get_value(today_ord, today_ord)
        v = values[0]

        if flask.request.method == "GET":
            return flask.render_template(
                "accounts/edit.jinja",
                account=ctx_account(acct, v),
            )

        form = flask.request.form
        institution = form["institution"].strip()
        name = form["name"].strip()
        number = form["number"].strip()
        category = form.get("category", type=AccountCategory)
        closed = "closed" in form
        emergency = "emergency" in form

        if category is None:
            return common.error("Account category must not be None")

        try:
            if closed and v != 0:
                msg = "Cannot close Account with non-zero balance"
                return common.error(msg)

            # Make the changes
            acct.institution = institution
            acct.name = name
            acct.number = number
            acct.category = category
            acct.closed = closed
            acct.emergency = emergency
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.overlay_swap(event="update-account")


def ctx_account(acct: Account, current_value: t.Real | None = None) -> t.DictAny:
    """Get the context to build the account details.

    Args:
        acct: Account to generate context for
        current_value: Current value to include, None will fetch

    Returns:
        Dictionary HTML context
    """
    today = datetime.date.today()
    today_ord = today.toordinal()
    if current_value is None:
        values, _, _ = acct.get_value(today_ord, today_ord)
        current_value = values[0]

    return {
        "uri": acct.uri,
        "name": acct.name,
        "number": acct.number,
        "institution": acct.institution,
        "category": acct.category,
        "category_type": AccountCategory,
        "value": current_value,
        "closed": acct.closed,
        "emergency": acct.emergency,
        "updated_days_ago": today_ord - (acct.updated_on_ord or today_ord),
        "opened_days_ago": today_ord - (acct.opened_on_ord or today_ord),
    }


def ctx_chart(acct: Account) -> t.DictAny:
    """Get the context to build the account chart.

    Args:
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    if start is None:
        opened_on_ord = acct.opened_on_ord
        start = (
            end if opened_on_ord is None else datetime.date.fromordinal(opened_on_ord)
        )
    no_defer = "no-defer" in args

    PREVIOUS_PERIOD["start"] = start
    PREVIOUS_PERIOD["end"] = end

    start_ord = start.toordinal()
    end_ord = end.toordinal()
    n = end_ord - start_ord + 1

    if n > web_utils.LIMIT_DEFER and not no_defer:
        return {
            "start": start,
            "end": end,
            "period": period,
            "defer": True,
        }

    values, profit, _ = acct.get_value(start_ord, end_ord)

    labels: t.Strings = []
    values_min: t.Reals | None = None
    values_max: t.Reals | None = None
    profit_min: t.Reals | None = None
    profit_max: t.Reals | None = None
    date_mode: str | None = None

    if n > web_utils.LIMIT_DOWNSAMPLE:
        # Downsample to min/avg/max by month
        labels, values_min, values, values_max = utils.downsample(
            start_ord,
            end_ord,
            values,
        )
        _, profit_min, profit, profit_max = utils.downsample(
            start_ord,
            end_ord,
            profit,
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
            "values": values,
            "min": values_min,
            "max": values_max,
            "profit": profit,
            "profit_min": profit_min,
            "profit_max": profit_max,
        },
    }


def ctx_assets(s: orm.Session, acct: Account) -> t.DictAny | None:
    """Get the context to build the account assets.

    Args:
        s: SQL session to use
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    args = flask.request.args

    period = args.get("period", DEFAULT_PERIOD)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    if start is None:
        opened_on_ord = acct.opened_on_ord
        start = (
            end if opened_on_ord is None else datetime.date.fromordinal(opened_on_ord)
        )

    start_ord = start.toordinal()
    end_ord = end.toordinal()

    asset_qtys = {
        a_id: qtys[0] for a_id, qtys in acct.get_asset_qty(end_ord, end_ord).items()
    }
    if len(asset_qtys) == 0:
        return None  # Not an investment account

    # Include assets that are currently held or had a change in qty
    query = s.query(TransactionSplit.asset_id).where(
        TransactionSplit.account_id == acct.id_,
        TransactionSplit.date_ord <= end_ord,
        TransactionSplit.date_ord >= start_ord,
        TransactionSplit.asset_id.is_not(None),
    )
    a_ids = {a_id for a_id, in query.distinct()}

    asset_qtys = {
        a_id: qty for a_id, qty in asset_qtys.items() if a_id in a_ids or qty != 0
    }
    a_ids = set(asset_qtys.keys())

    end_prices = Asset.get_value_all(s, end_ord, end_ord, ids=a_ids)

    asset_profits = acct.get_profit_by_asset(start_ord, end_ord)

    # Sum of profits should match final profit value, add any mismatch to cash

    query = (
        s.query(Asset)
        .with_entities(
            Asset.id_,
            Asset.name,
            Asset.category,
        )
        .where(Asset.id_.in_(a_ids))
    )

    assets: list[t.DictAny] = []
    total_value = Decimal(0)
    total_profit = Decimal(0)
    for a_id, name, category in query.yield_per(YIELD_PER):
        end_qty = asset_qtys[a_id]
        end_value = end_qty * end_prices[a_id][0]
        profit = asset_profits[a_id]

        total_value += end_value
        total_profit += profit

        ctx_asset = {
            "uri": Asset.id_to_uri(a_id),
            "category": category,
            "name": name,
            "end_qty": end_qty,
            "end_value": end_value,
            "profit": profit,
        }
        assets.append(ctx_asset)

    # Add in cash too
    cash: t.Real = (
        s.query(sqlalchemy.func.sum(TransactionSplit.amount))
        .where(TransactionSplit.account_id == acct.id_)
        .one()[0]
    )
    total_value += cash
    ctx_asset = {
        "uri": None,
        "category": AssetCategory.CASH,
        "name": "Cash",
        "end_qty": None,
        "end_value": cash,
        "profit": None,
    }
    assets.append(ctx_asset)

    for item in assets:
        item["end_value_ratio"] = (
            0 if total_value == 0 else item["end_value"] / total_value
        )

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


def page(uri: str) -> str:
    """GET /accounts/<uri>.

    Args:
        uri: Account URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        acct: Account = web_utils.find(s, Account, uri)  # type: ignore[attr-defined]
        return common.page(
            "accounts/index-content.jinja",
            acct=ctx_account(acct),
            chart=ctx_chart(acct),
            txn_table=transactions.ctx_table(acct, DEFAULT_PERIOD),
            assets=ctx_assets(s, acct),
        )


def table(uri: str) -> str:
    """GET /h/accounts/a/<uri>/table.

    Args:
        uri: Account URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        acct: Account = web_utils.find(s, Account, uri)  # type: ignore[attr-defined]

        args = flask.request.args
        period = args.get("period", DEFAULT_PERIOD)
        start, end = web_utils.parse_period(
            period,
            args.get("start", type=datetime.date.fromisoformat),
            args.get("end", type=datetime.date.fromisoformat),
        )
        if start is None:
            opened_on_ord = acct.opened_on_ord
            start = (
                end
                if opened_on_ord is None
                else datetime.date.fromordinal(opened_on_ord)
            )
        no_defer = "no-defer" in args
        if (
            PREVIOUS_PERIOD["start"] == start
            and PREVIOUS_PERIOD["end"] == end
            and flask.request.headers.get("Hx-Trigger") != "txn-table"
            and not no_defer
        ):
            # If same period and not being updated via update_transaction nor deferral:
            # don't update the chart
            # aka if just the table changed pages or column filters
            return flask.render_template(
                "accounts/table.jinja",
                txn_table=transactions.ctx_table(acct, DEFAULT_PERIOD),
                include_oob=True,
            )
        return flask.render_template(
            "accounts/table.jinja",
            chart=ctx_chart(acct),
            txn_table=transactions.ctx_table(acct, DEFAULT_PERIOD),
            assets=ctx_assets(s, acct),
            include_oob=True,
            include_chart_oob=True,
        )


def options(uri: str, field: str) -> str:
    """GET /h/accounts/a/<uri>/options/<field>/.

    Args:
        uri: Account URI
        field: Name of field to get options for

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        acct: Account = web_utils.find(s, Account, uri)  # type: ignore[attr-defined]
        args = flask.request.args

        id_mapping = None
        if field == "account":
            msg = "Cannot get account options for account transactions"
            raise exc.http.BadRequest(msg)
        if field == "category":
            id_mapping = TransactionCategory.map_name(s)

        period = args.get("period", "this-month")
        start, end = web_utils.parse_period(
            period,
            args.get("start", type=datetime.date.fromisoformat),
            args.get("end", type=datetime.date.fromisoformat),
        )
        end_ord = end.toordinal()

        query = s.query(TransactionSplit).where(
            TransactionSplit.asset_id.is_(None),
            TransactionSplit.date_ord <= end_ord,
            TransactionSplit.account_id == acct.id_,
        )
        if start is not None:
            start_ord = start.toordinal()
            query = query.where(TransactionSplit.date_ord >= start_ord)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "accounts/table-options.jinja",
            options=transactions.ctx_options(
                query,
                field,
                id_mapping,
                search_str=search_str,
            ),
            txn_table={"uri": uri},
            name=field,
            search_str=search_str,
        )


ROUTES: t.Routes = {
    "/accounts/<path:uri>": (page, ["GET"]),
    "/h/accounts/a/<path:uri>/table": (table, ["GET"]),
    "/h/accounts/a/<path:uri>/options/<path:field>": (options, ["GET"]),
    "/h/accounts/a/<path:uri>/edit": (edit, ["GET", "POST"]),
}
