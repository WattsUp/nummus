"""Account controllers."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common, transactions
from nummus.models import (
    Account,
    AccountCategory,
    TransactionCategory,
    TransactionSplit,
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

        _, values, _ = acct.get_value(today_ord, today_ord)
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
        _, values, _ = acct.get_value(today_ord, today_ord)
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
        "updated_days_ago": today_ord - acct.updated_on_ord,
        "opened_days_ago": today_ord - acct.opened_on_ord,
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
    start = start or datetime.date.fromordinal(acct.opened_on_ord)

    PREVIOUS_PERIOD["start"] = start
    PREVIOUS_PERIOD["end"] = end

    start_ord = start.toordinal()
    end_ord = end.toordinal()
    _, values, _ = acct.get_value(start_ord, end_ord)

    return {
        "start": start,
        "end": end,
        "period": period,
        "data": {
            "dates": [d.isoformat() for d in utils.range_date(start_ord, end_ord)],
            "values": values,
        },
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
        start = start or datetime.date.fromordinal(acct.opened_on_ord)
        if PREVIOUS_PERIOD["start"] == start and PREVIOUS_PERIOD["end"] == end:
            return common.page(
                "accounts/table.jinja",
                txn_table=transactions.ctx_table(acct, DEFAULT_PERIOD),
                include_oob=True,
            )
        return common.page(
            "accounts/table.jinja",
            chart=ctx_chart(acct),
            txn_table=transactions.ctx_table(acct, DEFAULT_PERIOD),
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

        query = s.query(TransactionSplit)
        query = query.where(TransactionSplit.asset_id.is_(None))
        if start is not None:
            start_ord = start.toordinal()
            query = query.where(TransactionSplit.date_ord >= start_ord)
        query = query.where(TransactionSplit.date_ord <= end_ord)
        query = query.where(TransactionSplit.account_id == acct.id_)

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
