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


class _AccountContext(TypedDict):
    """Type definition for Account context."""

    uri: str | None
    name: str
    number: str | None
    institution: str
    category: AccountCategory
    category_type: type[AccountCategory]
    closed: bool
    budgeted: bool
    updated_days_ago: int
    n_today: int
    change_today: Decimal
    value: Decimal

    performance: _PerformanceContext | None
    assets: list[_AssetContext] | None


class _PerformanceContext(TypedDict):
    """Context for performance metrics."""

    pnl_past_year: Decimal
    pnl_total: Decimal

    total_cost_basis: Decimal
    dividends: Decimal
    fees: Decimal
    cash: Decimal

    twrr: Decimal
    mwrr: Decimal

    labels: list[str]
    date_mode: str
    values: list[Decimal]
    cost_bases: list[Decimal]

    period: str
    period_options: dict[str, str]


class _AssetContext(TypedDict):
    """Context for assets held."""

    uri: str | None
    category: AssetCategory
    name: str
    ticker: str | None
    qty: Decimal | None
    price: Decimal
    value: Decimal
    value_ratio: Decimal
    profit: Decimal | None


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
        txn_table, title = transactions.ctx_table(acct.uri)
        title = title.removeprefix("Transactions").strip()
        title = f"Account {acct.name}, {title}" if title else f"Account {acct.name}"

        ctx = ctx_account(s, acct)
        if acct.category == AccountCategory.INVESTMENT:
            ctx["performance"] = ctx_performance(s, acct)
        ctx["assets"] = ctx_assets(s, acct)
        return common.page(
            "accounts/page.jinja",
            title=title,
            acct=ctx,
            txn_table=txn_table,
            endpoint="accounts.txns",
            url_args={"uri": uri},
        )


def new() -> str:
    """GET & POST /h/accounts/new.

    Returns:
        HTML response
    """
    raise NotImplementedError


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

        if flask.request.method == "GET":
            return flask.render_template(
                "accounts/edit.jinja",
                acct=ctx_account(s, acct),
            )

        values, _, _ = acct.get_value(today_ord, today_ord)
        v = values[0]

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
        if closed and v != 0:
            msg = "Cannot close Account with non-zero balance"
            return common.error(msg)

        try:
            with s.begin_nested():
                acct.institution = institution
                acct.name = name
                acct.number = number
                acct.category = category
                acct.closed = closed
                acct.budgeted = budgeted
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(
            event="update-account",
            snackbar="All changes saved",
        )


def performance(uri: str) -> flask.Response:
    """GET /h/accounts/a/<uri>/performance.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        acct = web_utils.find(s, Account, uri)
        html = flask.render_template(
            "accounts/performance.jinja",
            acct={
                "uri": uri,
                "performance": ctx_performance(s, acct),
            },
        )
    response = flask.make_response(html)
    response.headers["HX-Push-URL"] = flask.url_for(
        "accounts.page",
        uri=uri,
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **flask.request.args,
    )
    return response


def validation(uri: str) -> str:
    """GET /h/accounts/a/<uri>/validation.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    # dict{key: (required, prop if unique required)}
    properties: dict[str, tuple[bool, orm.QueryableAttribute | None]] = {
        "name": (True, Account.name),
        "institution": (True, None),
        "number": (False, Account.number),
    }

    args = flask.request.args
    for key, (required, prop) in properties.items():
        if key not in args:
            continue
        value = args[key].strip()
        if value == "":
            return "Required" if required else ""
        if len(value) < utils.MIN_STR_LEN:
            return f"{utils.MIN_STR_LEN} characters required"
        if prop is not None:
            with p.begin_session() as s:
                n = (
                    s.query(Account)
                    .where(
                        prop == value,
                        Account.id_ != Account.uri_to_id(uri),
                    )
                    .count()
                )
                if n != 0:
                    return "Must be unique"
        return ""

    msg = f"Account validation for {args} not implemented"
    raise NotImplementedError(msg)


def ctx_account(
    s: orm.Session,
    acct: Account,
    *,
    skip_today: bool = False,
) -> _AccountContext:
    """Get the context to build the account details.

    Args:
        s: SQL session to use
        acct: Account to generate context for
        skip_today: True will skip fetching today's value

    Returns:
        Dictionary HTML context
    """
    today = datetime.date.today()
    today_ord = today.toordinal()
    if skip_today:
        current_value = Decimal(0)
        change_today = Decimal(0)
        n_today = 0
        updated_on_ord = today_ord
    else:
        updated_on_ord = acct.updated_on_ord or today_ord

        query = (
            s.query(Transaction)
            .with_entities(
                func.count(Transaction.id_),
                func.sum(Transaction.amount),
            )
            .where(
                Transaction.date_ord == today_ord,
                Transaction.account_id == acct.id_,
            )
        )
        n_today, change_today = query.one()

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
        "budgeted": acct.budgeted,
        "updated_days_ago": today_ord - updated_on_ord,
        "change_today": change_today,
        "n_today": n_today,
        "performance": None,
        "assets": [],
    }


def ctx_performance(s: orm.Session, acct: Account) -> _PerformanceContext:
    """Get the context to build the account performance details.

    Args:
        s: SQL session to use
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    period = flask.request.args.get("chart-period", "1yr")
    start, end = web_utils.parse_period(period)
    end_ord = end.toordinal()
    start_ord = acct.opened_on_ord or end_ord if start is None else start.toordinal()
    labels, date_mode = web_utils.date_labels(start_ord, end_ord)

    query = s.query(TransactionCategory.id_, TransactionCategory.name).where(
        TransactionCategory.is_profit_loss.is_(True),
    )
    pnl_categories: dict[int, str] = dict(query.all())  # type: ignore[attr-defined]

    # Calculate total cost basis
    total_cost_basis = Decimal(0)
    dividends = Decimal(0)
    fees = Decimal(0)
    query = (
        s.query(TransactionSplit)
        .with_entities(TransactionSplit.category_id, func.sum(TransactionSplit.amount))
        .where(TransactionSplit.account_id == acct.id_)
        .group_by(TransactionSplit.category_id)
    )
    for cat_id, value in query.yield_per(YIELD_PER):
        name = pnl_categories.get(cat_id)
        if name is None:
            total_cost_basis += value
        elif "dividend" in name:
            dividends += value
        elif "fee" in name:
            fees += value

    values, profits, asset_values = acct.get_value(start_ord, end_ord)

    cash = values[-1] - sum(v[-1] for v in asset_values.values())

    n = len(labels)
    twrr = utils.twrr(values, profits)[-1]
    twrr_per_annum = (1 + twrr) ** (utils.DAYS_IN_YEAR / n) - 1

    return {
        "pnl_past_year": profits[-1],
        "pnl_total": values[-1] - total_cost_basis,
        "total_cost_basis": total_cost_basis,
        "dividends": dividends,
        "fees": fees,
        "cash": cash,
        "twrr": twrr_per_annum,
        "mwrr": utils.mwrr(values, profits),
        "labels": labels,
        "date_mode": date_mode,
        "values": values,
        "cost_bases": [v - p for v, p in zip(values, profits, strict=True)],
        "period": period,
        "period_options": web_utils.PERIOD_OPTIONS,
    }


def ctx_assets(s: orm.Session, acct: Account) -> list[_AssetContext] | None:
    """Get the context to build the account assets.

    Args:
        s: SQL session to use
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    today = datetime.date.today()
    today_ord = today.toordinal()
    start_ord = acct.opened_on_ord or today_ord

    asset_qtys = {
        a_id: qtys[0] for a_id, qtys in acct.get_asset_qty(today_ord, today_ord).items()
    }
    if len(asset_qtys) == 0:
        return None  # Not an investment account

    # Include all assets every held
    query = s.query(TransactionSplit.asset_id).where(
        TransactionSplit.account_id == acct.id_,
        TransactionSplit.asset_id.is_not(None),
    )
    a_ids = {a_id for a_id, in query.distinct()}

    end_prices = Asset.get_value_all(s, today_ord, today_ord, ids=a_ids)
    asset_profits = acct.get_profit_by_asset(start_ord, today_ord)

    # Sum of profits should match final profit value, add any mismatch to cash

    query = (
        s.query(Asset)
        .with_entities(
            Asset.id_,
            Asset.name,
            Asset.ticker,
            Asset.category,
        )
        .where(Asset.id_.in_(a_ids))
    )

    assets: list[_AssetContext] = []
    total_value = Decimal(0)
    total_profit = Decimal(0)
    for a_id, name, ticker, category in query.yield_per(YIELD_PER):
        end_qty = asset_qtys[a_id]
        end_price = end_prices[a_id][0]
        end_value = end_qty * end_price
        profit = asset_profits[a_id]

        total_value += end_value
        total_profit += profit

        ctx_asset: _AssetContext = {
            "uri": Asset.id_to_uri(a_id),
            "category": category,
            "name": name,
            "ticker": ticker,
            "qty": end_qty,
            "price": end_price,
            "value": end_value,
            "value_ratio": Decimal(0),
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
        "ticker": None,
        "qty": None,
        "price": Decimal(1),
        "value": cash,
        "value_ratio": Decimal(0),
        "profit": None,
    }
    assets.append(ctx_asset)

    for item in assets:
        item["value_ratio"] = (
            Decimal(0) if total_value == 0 else item["value"] / total_value
        )

    return sorted(
        assets,
        key=lambda item: (
            item["value"] == 0,
            0 if item["profit"] is None else -item["profit"],
            -item["value"],
            item["name"].lower(),
        ),
    )


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

    categories_total: dict[AccountCategory, Decimal] = defaultdict(Decimal)
    categories: dict[AccountCategory, list[_AccountContext]] = defaultdict(list)

    n_closed = 0
    with p.begin_session() as s:
        # Get basic info
        accounts: dict[int, _AccountContext] = {}
        query = s.query(Account).order_by(Account.category)
        if not include_closed:
            query = query.where(Account.closed.is_(False))
        for acct in query.all():
            accounts[acct.id_] = ctx_account(s, acct, skip_today=True)
            if acct.closed:
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


def txns(uri: str) -> str | flask.Response:
    """GET /h/accounts/a/<uri>/txns.

    Args:
        uri: Account URI

    Returns:
        HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args
    first_page = "page" not in args

    txn_table, title = transactions.ctx_table(uri)
    title = title.removeprefix("Transactions").strip()
    with p.begin_session() as s:
        acct = web_utils.find(s, Account, uri)
        title = f"Account {acct.name}, {title}" if title else f"Account {acct.name}"
    html_title = f"<title>{title} - nummus</title>\n"
    html = html_title + flask.render_template(
        "transactions/table-rows.jinja",
        acct={"uri": uri},
        ctx=txn_table,
        endpoint="accounts.txns",
        url_args={"uri": uri},
        include_oob=first_page,
    )
    if not first_page:
        # Don't push URL for following pages
        return html
    response = flask.make_response(html)
    response.headers["HX-Push-URL"] = flask.url_for(
        "accounts.page",
        uri=uri,
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **flask.request.args,
    )
    return response


def txns_options(uri: str) -> str:
    """GET /h/accounts/a/<uri>/txns-options.

    Args:
        uri: Account URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        accounts = Account.map_name(s)
        categories_emoji = TransactionCategory.map_name_emoji(s)

        args = flask.request.args
        uncleared = "uncleared" in args
        selected_account = uri
        selected_category = args.get("category")
        selected_period = args.get("period")
        selected_start = args.get("start")
        selected_end = args.get("end")

        query, _ = transactions.table_query(
            s,
            None,
            selected_account,
            selected_period,
            selected_start,
            selected_end,
            selected_category,
            uncleared=uncleared,
        )
        options = transactions.ctx_options(
            query,
            accounts,
            categories_emoji,
            selected_account,
            selected_category,
        )

        return flask.render_template(
            "transactions/table-filters.jinja",
            only_inner=True,
            acct={"uri": uri},
            ctx={
                **options,
                "selected_period": selected_period,
                "selected_account": selected_account,
                "selected_category": selected_category,
                "uncleared": uncleared,
                "start": selected_start,
                "end": selected_end,
            },
            endpoint="accounts.txns",
            url_args={"uri": uri},
        )


ROUTES: Routes = {
    "/accounts": (page_all, ["GET"]),
    "/accounts/<path:uri>": (page, ["GET"]),
    "/h/accounts/new": (new, ["GET", "POST"]),
    "/h/accounts/a/<path:uri>": (account, ["GET", "PUT"]),
    "/h/accounts/a/<path:uri>/performance": (performance, ["GET"]),
    "/h/accounts/a/<path:uri>/validation": (validation, ["GET"]),
    "/h/accounts/a/<path:uri>/txns": (txns, ["GET"]),
    "/h/accounts/a/<path:uri>/txns-options": (txns_options, ["GET"]),
}
