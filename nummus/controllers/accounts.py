"""Account controllers."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common, transactions
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus.controllers.base import Routes

PREVIOUS_PERIOD: dict[str, datetime.date | None] = {"start": None, "end": None}


def account(uri: str) -> str | flask.Response:
    """GET & POST /h/accounts/a/<uri>.

    Args:
        uri: Account URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    with p.begin_session() as s:
        acct = web_utils.find(s, Account, uri)

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
        category_s = form.get("category")
        category = AccountCategory(category_s) if category_s else None
        closed = "closed" in form
        budgeted = "budgeted" in form

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
            acct.budgeted = budgeted
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(event="update-account")


def ctx_account(
    acct: Account,
    current_value: Decimal | None = None,
) -> dict[str, object]:
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
    updated_on_ord = acct.updated_on_ord or today_ord

    return {
        "uri": acct.uri,
        "name": acct.name,
        "number": acct.number,
        "institution": acct.institution,
        "category": acct.category,
        "category_type": AccountCategory,
        "value": current_value,
        "updated_on": datetime.date.fromordinal(updated_on_ord),
        "closed": acct.closed,
        "budgeted": acct.budgeted,
        "updated_days_ago": today_ord - updated_on_ord,
        "opened_days_ago": today_ord - (acct.opened_on_ord or today_ord),
    }


def ctx_chart(acct: Account) -> dict[str, object]:
    """Get the context to build the account chart.

    Args:
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    args = flask.request.args

    period = args.get("period", transactions.DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
    if start is None:
        opened_on_ord = acct.opened_on_ord
        start = (
            end if opened_on_ord is None else datetime.date.fromordinal(opened_on_ord)
        )

    PREVIOUS_PERIOD["start"] = start
    PREVIOUS_PERIOD["end"] = end

    start_ord = start.toordinal()
    end_ord = end.toordinal()
    n = end_ord - start_ord + 1

    values, profit, _ = acct.get_value(start_ord, end_ord)

    labels: list[str] = []
    values_min: list[Decimal] | None = None
    values_max: list[Decimal] | None = None
    profit_min: list[Decimal] | None = None
    profit_max: list[Decimal] | None = None
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


def ctx_assets(s: orm.Session, acct: Account) -> dict[str, object] | None:
    """Get the context to build the account assets.

    Args:
        s: SQL session to use
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    args = flask.request.args

    period = args.get("period", transactions.DEFAULT_PERIOD)
    start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
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

    class AssetContext(TypedDict):
        """Type definition for Asset context."""

        uri: str | None
        category: AssetCategory
        name: str
        end_qty: Decimal | None
        end_value: Decimal
        end_value_ratio: Decimal
        profit: Decimal | None

    assets: list[AssetContext] = []
    total_value = Decimal(0)
    total_profit = Decimal(0)
    for a_id, name, category in query.yield_per(YIELD_PER):
        end_qty = asset_qtys[a_id]
        end_value = end_qty * end_prices[a_id][0]
        profit = asset_profits[a_id]

        total_value += end_value
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
    cash: Decimal = (
        s.query(func.sum(TransactionSplit.amount))
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
        "end_value_ratio": Decimal(0),
        "profit": None,
    }
    assets.append(ctx_asset)

    for item in assets:
        item["end_value_ratio"] = (
            Decimal(0) if total_value == 0 else item["end_value"] / total_value
        )

    assets = sorted(
        assets,
        key=lambda item: (
            -item["end_value"],
            0 if item["profit"] is None else -item["profit"],
            item["name"].lower(),
        ),
    )

    return {
        "assets": assets,
        "end_value": total_value,
        "profit": total_profit,
    }


def ctx_accounts(*, include_closed: bool = False) -> dict[str, object]:
    """Get the context to build the accounts table.

    Args:
        include_closed: True will include Accounts marked closed, False will exclude

    Returns:
        Dictionary HTML context
    """
    # Create sidebar context
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.date.today()
    today_ord = today.toordinal()

    assets = Decimal(0)
    liabilities = Decimal(0)

    class AccountContext(TypedDict):
        """Type definition for Account context."""

        uri: str | None
        name: str
        category: AccountCategory
        closed: bool
        updated_days_ago: int
        n_today: int
        change_today: Decimal
        value: Decimal

    categories_total: dict[AccountCategory, Decimal] = defaultdict(Decimal)
    categories: dict[AccountCategory, list[AccountContext]] = defaultdict(list)

    n_closed = 0
    with p.begin_session() as s:
        # Get basic info
        accounts: dict[int, AccountContext] = {}
        query = (
            s.query(Account)
            .with_entities(
                Account.id_,
                Account.name,
                Account.category,
                Account.closed,
            )
            .order_by(Account.category)
        )
        if not include_closed:
            query = query.where(Account.closed.is_(False))
        for acct_id, name, category, closed in query.all():
            acct_id: int
            name: str
            category: AccountCategory
            closed: bool
            accounts[acct_id] = {
                "uri": Account.id_to_uri(acct_id),
                "name": name,
                "category": category,
                "closed": closed,
                "updated_days_ago": 0,
                "n_today": 0,
                "change_today": Decimal(0),
                "value": Decimal(0),
            }
            if closed:
                n_closed += 1

        # Get updated_on
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.account_id,
                func.max(Transaction.date_ord),
            )
            .group_by(Transaction.account_id)
            .where(Transaction.account_id.in_(accounts))
        )
        for acct_id, updated_on_ord in query.all():
            acct_id: int
            updated_on_ord: int
            accounts[acct_id]["updated_days_ago"] = today_ord - updated_on_ord

        # Get n_today
        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.account_id,
                func.count(Transaction.id_),
                func.sum(Transaction.amount),
            )
            .where(Transaction.date_ord == today_ord)
            .group_by(Transaction.account_id)
            .where(Transaction.account_id.in_(accounts))
        )
        for acct_id, n_today, change_today in query.all():
            acct_id: int
            n_today: int
            change_today: Decimal
            accounts[acct_id]["n_today"] = n_today
            accounts[acct_id]["change_today"] = change_today

        # Get all Account values
        acct_values, _, _ = Account.get_value_all(s, today_ord, today_ord, ids=accounts)
        for acct_id, ctx in accounts.items():
            v = acct_values[acct_id][0]
            if v > 0:
                assets += v
            else:
                liabilities += v
            ctx["value"] = v
            category = ctx["category"]

            categories_total[category] += v
            categories[category].append(ctx)

    bar_total = assets - liabilities
    if bar_total == 0:
        asset_width = 0
        liabilities_width = 0
    else:
        asset_width = round(assets / (assets - liabilities) * 100, 2)
        liabilities_width = 100 - asset_width

    # Removed empty categories and sort
    categories = {
        cat: sorted(accounts, key=lambda acct: acct["name"])
        for cat, accounts in categories.items()
        if len(accounts) > 0
    }

    return {
        "net_worth": assets + liabilities,
        "assets": assets,
        "liabilities": liabilities,
        "assets_w": asset_width,
        "liabilities_w": liabilities_width,
        "categories": {
            cat: (categories_total[cat], accounts)
            for cat, accounts in categories.items()
        },
        "include_closed": include_closed,
        "n_closed": n_closed,
    }


def page_all() -> flask.Response:
    """GET /accounts.

    Returns:
        string HTML response
    """
    include_closed = "include-closed" in flask.request.args
    return common.page(
        "accounts/page-all.jinja",
        "Accounts",
        ctx=ctx_accounts(include_closed=include_closed),
    )


def page(uri: str) -> flask.Response:
    """GET /accounts/<uri>.

    Args:
        uri: Account URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        acct = web_utils.find(s, Account, uri)
        txn_table, title = transactions.ctx_table(acct, transactions.DEFAULT_PERIOD)
        title = f"Account {acct.name}," + title.removeprefix("Transactions")
        return common.page(
            "accounts/index-content.jinja",
            title=title,
            acct=ctx_account(acct),
            chart=ctx_chart(acct),
            txn_table=txn_table,
            assets=ctx_assets(s, acct),
            endpoint="accounts.txns",
            endpoint_new="accounts.new_txn",
            url_args={"uri": uri},
            no_account_column=True,
        )


def txns(uri: str) -> flask.Response:
    """GET /h/accounts/a/<uri>/txns.

    Args:
        uri: Account URI

    Returns:
        HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        acct = web_utils.find(s, Account, uri)

        args = flask.request.args
        period = args.get("period", transactions.DEFAULT_PERIOD)
        start, end = web_utils.parse_period(period, args.get("start"), args.get("end"))
        if start is None:
            opened_on_ord = acct.opened_on_ord
            start = (
                end
                if opened_on_ord is None
                else datetime.date.fromordinal(opened_on_ord)
            )
        txn_table, title = transactions.ctx_table(acct, transactions.DEFAULT_PERIOD)
        title = f"Account {acct.name}," + title.removeprefix("Transactions")
        html = f"<title>{title}</title>\n" + flask.render_template(
            "transactions/table.jinja",
            txn_table=txn_table,
            include_oob=True,
            endpoint="accounts.txns",
            endpoint_new="accounts.new_txn",
            url_args={"uri": uri},
            no_account_column=True,
        )
        if not (
            PREVIOUS_PERIOD["start"] == start
            and PREVIOUS_PERIOD["end"] == end
            and flask.request.headers.get("Hx-Trigger") != "txn-table"
        ):
            # If same period and not being updated via update_transaction:
            # don't update the chart
            # aka if just the table changed pages or column filters
            html += flask.render_template(
                "accounts/chart-data.jinja",
                oob=True,
                chart=ctx_chart(acct),
                url_args={"uri": uri},
            )
            ctx = ctx_assets(s, acct)
            if ctx:
                html += flask.render_template(
                    "accounts/assets.jinja",
                    oob=True,
                    assets=ctx,
                )
        response = flask.make_response(html)
        args = dict(flask.request.args.lists())
        response.headers["HX-Push-Url"] = flask.url_for(
            "accounts.page",
            _anchor=None,
            _method=None,
            _scheme=None,
            _external=False,
            uri=uri,
            **args,
        )
        return response


def txns_options(uri: str, field: str) -> str:
    """GET /h/accounts/a/<uri>/txn-options/<field>.

    Args:
        uri: Account URI
        field: Name of field to get options for

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        acct = web_utils.find(s, Account, uri)
        args = flask.request.args

        id_mapping = None
        label_mapping = None
        if field == "account":
            msg = "Cannot get account options for account transactions"
            raise exc.http.BadRequest(msg)
        if field == "category":
            id_mapping = TransactionCategory.map_name(s)
            label_mapping = TransactionCategory.map_name_emoji(s)
        elif field not in {"payee", "tag"}:
            msg = f"Unexpected txns options: {field}"
            raise exc.http.BadRequest(msg)

        query, _, _, _ = transactions.table_unfiltered_query(s, acct=acct)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "transactions/table-options.jinja",
            options=transactions.ctx_options(
                query,
                field,
                id_mapping,
                label_mapping=label_mapping,
                search_str=search_str,
            ),
            txn_table={"uri": uri},
            name=field,
            search_str=search_str,
            endpoint="accounts.txns",
            endpoint_new="accounts.new_txn",
            url_args={"uri": uri},
            no_account_column=True,
        )


def new_txn(uri: str) -> str | flask.Response:
    """GET & POST /h/accounts/a/<uri>/new-txn.

    Args:
        uri: Account URI

    Returns:
        HTML response
    """
    return transactions.new(uri)


def new() -> str:
    """GET & POST /h/accounts/new.

    Returns:
        HTML response
    """
    raise NotImplementedError


ROUTES: Routes = {
    "/accounts": (page_all, ["GET"]),
    "/accounts/<path:uri>": (page, ["GET"]),
    "/h/accounts/new": (new, ["GET", "POST"]),
    "/h/accounts/a/<path:uri>/txns": (txns, ["GET"]),
    "/h/accounts/a/<path:uri>/txns-options/<path:field>": (txns_options, ["GET"]),
    "/h/accounts/a/<path:uri>": (account, ["GET", "PUT"]),
    "/h/accounts/a/<path:uri>/new-txn": (new_txn, ["GET", "POST"]),
}
