"""Account controllers."""

from __future__ import annotations

import operator
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func

from nummus import exceptions as exc
from nummus import utils, web
from nummus.controllers import base, transactions
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    query_to_dict,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    import datetime

    import werkzeug
    from sqlalchemy import orm


class AccountContext(TypedDict):
    """Type definition for Account context."""

    uri: str | None
    name: str
    number: str | None
    institution: str
    category: AccountCategory
    category_type: type[AccountCategory]
    closed: bool
    budgeted: bool
    updated_days_ago: int | None
    n_today: int
    n_future: int
    change_today: Decimal
    change_future: Decimal
    value: Decimal

    performance: PerformanceContext | None
    assets: list[AssetContext] | None


class PerformanceContext(TypedDict):
    """Context for performance metrics."""

    pnl_past_year: Decimal
    pnl_total: Decimal

    total_cost_basis: Decimal
    dividends: Decimal
    fees: Decimal
    cash: Decimal

    twrr: Decimal
    mwrr: Decimal | None

    labels: list[str]
    mode: str

    avg: list[Decimal]
    cost_basis: list[Decimal]

    period: str
    period_options: dict[str, str]


class AssetContext(TypedDict):
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


class AllAccountsContext(TypedDict):
    """Context for page_all Accounts."""

    net_worth: Decimal
    assets: Decimal
    liabilities: Decimal
    assets_w: Decimal
    liabilities_w: Decimal
    categories: dict[AccountCategory, tuple[Decimal, list[AccountContext]]]
    include_closed: bool
    n_closed: int


def page_all() -> flask.Response:
    """GET /accounts.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        include_closed = "include-closed" in flask.request.args
        return base.page(
            "accounts/page-all.jinja",
            "Accounts",
            ctx=ctx_accounts(s, base.today_client(), include_closed=include_closed),
        )


def page(uri: str) -> flask.Response:
    """GET /accounts/<uri>.

    Args:
        uri: Account URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    today = base.today_client()
    with p.begin_session() as s:
        acct = base.find(s, Account, uri)
        args = flask.request.args
        txn_table, title = transactions.ctx_table(
            s,
            today,
            args.get("search"),
            args.get("account"),
            args.get("category"),
            args.get("period"),
            args.get("start"),
            args.get("end"),
            args.get("page"),
            uncleared="uncleared" in args,
            acct_uri=acct.uri,
        )
        title = title.removeprefix("Transactions").strip()
        title = f"{acct.name}, {title}" if title else f"{acct.name}"

        ctx = ctx_account(s, acct, today)
        if acct.category == AccountCategory.INVESTMENT:
            ctx["performance"] = ctx_performance(
                s,
                acct,
                today,
                args.get("chart-period"),
            )
        ctx["assets"] = ctx_assets(s, acct, today)
        return base.page(
            "accounts/page.jinja",
            title=title,
            acct=ctx,
            txn_table=txn_table,
            endpoint="accounts.txns",
            url_args={"uri": uri},
        )


def new() -> str | flask.Response:
    """GET & POST /h/accounts/new.

    Returns:
        HTML response

    """
    if flask.request.method == "GET":
        ctx: AccountContext = {
            "uri": None,
            "name": "",
            "number": None,
            "institution": "",
            "category": AccountCategory.CASH,
            "category_type": AccountCategory,
            "closed": False,
            "budgeted": False,
            "updated_days_ago": None,
            "n_today": 0,
            "n_future": 0,
            "change_today": Decimal(),
            "change_future": Decimal(),
            "value": Decimal(),
            "performance": None,
            "assets": None,
        }
        return flask.render_template(
            "accounts/edit.jinja",
            acct=ctx,
        )

    p = web.portfolio

    with p.begin_session() as s:
        form = flask.request.form
        institution = form["institution"].strip()
        name = form["name"].strip()
        number = form["number"].strip()
        category = AccountCategory(form["category"])
        budgeted = "budgeted" in form

        try:
            with s.begin_nested():
                acct = Account(
                    institution=institution,
                    name=name,
                    number=number,
                    category=category,
                    closed=False,
                    budgeted=budgeted,
                )
                s.add(acct)
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(event="account", snackbar="All changes saved")


def account(uri: str) -> str | werkzeug.Response:
    """GET & POST /h/accounts/a/<uri>.

    Args:
        uri: Account URI

    Returns:
        string HTML response

    """
    p = web.portfolio
    today = base.today_client()
    today_ord = today.toordinal()

    with p.begin_session() as s:
        acct = base.find(s, Account, uri)

        if flask.request.method == "GET":
            return flask.render_template(
                "accounts/edit.jinja",
                acct=ctx_account(s, acct, today),
            )
        if flask.request.method == "DELETE":
            with s.begin_nested():
                s.delete(acct)
            return flask.redirect(flask.url_for("accounts.page_all"))

        values, _, _ = acct.get_value(today_ord, today_ord)
        v = values[0]

        form = flask.request.form
        institution = form["institution"].strip()
        name = form["name"].strip()
        number = form["number"].strip()
        category = AccountCategory(form["category"])
        closed = "closed" in form
        budgeted = "budgeted" in form

        if closed and v != 0:
            msg = "Cannot close Account with non-zero balance"
            return base.error(msg)

        try:
            with s.begin_nested():
                acct.institution = institution
                acct.name = name
                acct.number = number
                acct.category = category
                acct.closed = closed
                acct.budgeted = budgeted
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(event="account", snackbar="All changes saved")


def performance(uri: str) -> flask.Response:
    """GET /h/accounts/a/<uri>/performance.

    Returns:
        string HTML response

    """
    p = web.portfolio
    args = flask.request.args
    with p.begin_session() as s:
        acct = base.find(s, Account, uri)
        html = flask.render_template(
            "accounts/performance.jinja",
            acct={
                "uri": uri,
                "performance": ctx_performance(
                    s,
                    acct,
                    base.today_client(),
                    args.get("chart-period"),
                ),
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
        **args,
    )
    return response


def validation() -> str:
    """GET /h/accounts/validation.

    Returns:
        string HTML response

    """
    p = web.portfolio

    # dict{key: (required, prop if unique required)}
    properties: dict[str, tuple[bool, orm.QueryableAttribute | None]] = {
        "name": (True, Account.name),
        "institution": (True, None),
        "number": (False, Account.number),
    }

    with p.begin_session() as s:
        args = flask.request.args
        uri = args.get("uri")
        for key, (required, prop) in properties.items():
            if key not in args:
                continue
            return base.validate_string(
                args[key],
                is_required=required,
                session=s,
                no_duplicates=prop,
                no_duplicate_wheres=(
                    None if uri is None else [Account.id_ != Account.uri_to_id(uri)]
                ),
            )

    raise NotImplementedError


def ctx_account(
    s: orm.Session,
    acct: Account,
    today: datetime.date,
    *,
    skip_today: bool = False,
) -> AccountContext:
    """Get the context to build the account details.

    Args:
        s: SQL session to use
        acct: Account to generate context for
        today: Today's date
        skip_today: True will skip fetching today's value

    Returns:
        Dictionary HTML context

    """
    today_ord = today.toordinal()
    if skip_today:
        current_value = Decimal()
        change_today = Decimal()
        change_future = Decimal()
        n_today = 0
        n_future = 0
        updated_days_ago = None
    else:
        updated_on_ord = acct.updated_on_ord
        updated_days_ago = (
            None if updated_on_ord is None else today_ord - updated_on_ord
        )

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
        change_today: Decimal = change_today or Decimal()

        query = (
            s.query(Transaction)
            .with_entities(
                func.count(Transaction.id_),
                func.sum(Transaction.amount),
            )
            .where(
                Transaction.date_ord > today_ord,
                Transaction.account_id == acct.id_,
            )
        )
        n_future, change_future = query.one()

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
        "updated_days_ago": updated_days_ago,
        "change_today": change_today,
        "change_future": change_future or Decimal(),
        "n_today": n_today,
        "n_future": n_future,
        "performance": None,
        "assets": [],
    }


def ctx_performance(
    s: orm.Session,
    acct: Account,
    today: datetime.date,
    period: str | None,
) -> PerformanceContext:
    """Get the context to build the account performance details.

    Args:
        s: SQL session to use
        acct: Account to generate context for
        today: Today's date
        period: Period string to get data for

    Returns:
        Dictionary HTML context

    """
    period = period or "1yr"
    start, end = base.parse_period(period, today)
    end_ord = end.toordinal()
    start_ord = acct.opened_on_ord or end_ord if start is None else start.toordinal()

    query = s.query(TransactionCategory.id_, TransactionCategory.name).where(
        TransactionCategory.is_profit_loss.is_(True),
    )
    pnl_categories: dict[int, str] = query_to_dict(query)

    # Calculate total cost basis
    total_cost_basis = Decimal()
    dividends = Decimal()
    fees = Decimal()
    query = (
        s.query(TransactionSplit)
        .with_entities(TransactionSplit.category_id, func.sum(TransactionSplit.amount))
        .where(
            TransactionSplit.date_ord <= end_ord,
            TransactionSplit.account_id == acct.id_,
        )
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
    cost_basis = [v - p for v, p in zip(values, profits, strict=True)]

    cash = values[-1] - sum(v[-1] for v in asset_values.values())

    n = len(values)
    twrr = utils.twrr(values, profits)[-1]
    twrr_per_annum = (
        Decimal(-1) if twrr < -1 else (1 + twrr) ** (utils.DAYS_IN_YEAR / n) - 1
    )

    chart_values, chart_cost_basis = base.chart_data(
        start_ord,
        end_ord,
        (values, cost_basis),
    )

    return {
        "pnl_past_year": profits[-1],
        "pnl_total": values[-1] - total_cost_basis,
        "total_cost_basis": total_cost_basis,
        "dividends": dividends,
        "fees": fees,
        "cash": cash,
        "twrr": twrr_per_annum,
        "mwrr": utils.mwrr(values, profits),
        "labels": chart_values["labels"],
        "mode": chart_values["mode"],
        "avg": chart_values["avg"],
        "cost_basis": chart_cost_basis["avg"],
        "period": period,
        "period_options": base.PERIOD_OPTIONS,
    }


def ctx_assets(
    s: orm.Session,
    acct: Account,
    today: datetime.date,
) -> list[AssetContext] | None:
    """Get the context to build the account assets.

    Args:
        s: SQL session to use
        acct: Account to generate context for
        today: Today's date

    Returns:
        Dictionary HTML context

    """
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

    assets: list[AssetContext] = []
    total_value = Decimal()
    total_profit = Decimal()
    for a_id, name, ticker, category in query.yield_per(YIELD_PER):
        end_qty = asset_qtys[a_id]
        end_price = end_prices[a_id][0]
        end_value = end_qty * end_price
        profit = asset_profits[a_id]

        total_value += end_value
        total_profit += profit

        ctx_asset: AssetContext = {
            "uri": Asset.id_to_uri(a_id),
            "category": category,
            "name": name,
            "ticker": ticker,
            "qty": end_qty,
            "price": end_price,
            "value": end_value,
            "value_ratio": Decimal(),
            "profit": profit,
        }
        assets.append(ctx_asset)

    # Add in cash too
    cash: Decimal = (
        s.query(func.sum(TransactionSplit.amount))
        .where(TransactionSplit.account_id == acct.id_)
        .where(TransactionSplit.date_ord <= today_ord)
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
        "value_ratio": Decimal(),
        "profit": None,
    }
    assets.append(ctx_asset)

    for item in assets:
        item["value_ratio"] = (
            Decimal() if total_value == 0 else item["value"] / total_value
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


def ctx_accounts(
    s: orm.Session,
    today: datetime.date,
    *,
    include_closed: bool = False,
) -> AllAccountsContext:
    """Get the context to build the accounts table.

    Args:
        s: SQL session to use
        today: Today's date
        include_closed: True will include Accounts marked closed, False will exclude

    Returns:
        AllAccountsContext

    """
    # Create sidebar context
    today_ord = today.toordinal()

    assets = Decimal()
    liabilities = Decimal()

    categories_total: dict[AccountCategory, Decimal] = defaultdict(Decimal)
    categories: dict[AccountCategory, list[AccountContext]] = defaultdict(list)

    n_closed = 0
    # Get basic info
    accounts: dict[int, AccountContext] = {}
    query = s.query(Account).order_by(Account.category)
    if not include_closed:
        query = query.where(Account.closed.is_(False))
    for acct in query.all():
        accounts[acct.id_] = ctx_account(s, acct, today, skip_today=True)
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
        change_today: Decimal | None
        accounts[acct_id]["n_today"] = n_today
        accounts[acct_id]["change_today"] = change_today or Decimal()

    # Get n_future
    query = (
        s.query(Transaction)
        .with_entities(
            Transaction.account_id,
            func.count(Transaction.id_),
            func.sum(Transaction.amount),
        )
        .where(Transaction.date_ord > today_ord)
        .group_by(Transaction.account_id)
        .where(Transaction.account_id.in_(accounts))
    )
    for acct_id, n_future, change_future in query.all():
        acct_id: int
        n_future: int
        change_future: Decimal
        accounts[acct_id]["n_future"] = n_future
        accounts[acct_id]["change_future"] = change_future

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
        asset_width = Decimal()
        liabilities_width = Decimal()
    else:
        asset_width = round(assets / (assets - liabilities) * 100, 2)
        liabilities_width = 100 - asset_width

    # Removed empty categories and sort
    categories = {
        cat: sorted(accounts, key=operator.itemgetter("name"))
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
    p = web.portfolio
    args = flask.request.args
    first_page = "page" not in args

    with p.begin_session() as s:
        txn_table, title = transactions.ctx_table(
            s,
            base.today_client(),
            args.get("search"),
            args.get("account"),
            args.get("category"),
            args.get("period"),
            args.get("start"),
            args.get("end"),
            args.get("page"),
            uncleared="uncleared" in args,
            acct_uri=uri,
        )
        title = title.removeprefix("Transactions").strip()
        acct = base.find(s, Account, uri)
        title = f"{acct.name}, {title}" if title else f"{acct.name}"
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
    p = web.portfolio
    with p.begin_session() as s:
        accounts = Account.map_name(s)

        args = flask.request.args
        uncleared = "uncleared" in args
        selected_account = uri
        selected_category = args.get("category")
        selected_period = args.get("period")
        selected_start = args.get("start")
        selected_end = args.get("end")

        tbl_query = transactions.table_query(
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
            tbl_query,
            base.today_client(),
            accounts,
            base.tranaction_category_groups(s),
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


ROUTES: base.Routes = {
    "/accounts": (page_all, ["GET"]),
    "/accounts/<path:uri>": (page, ["GET"]),
    "/h/accounts/new": (new, ["GET", "POST"]),
    "/h/accounts/a/<path:uri>": (account, ["GET", "PUT", "DELETE"]),
    "/h/accounts/a/<path:uri>/performance": (performance, ["GET"]),
    "/h/accounts/a/<path:uri>/txns": (txns, ["GET"]),
    "/h/accounts/a/<path:uri>/txns-options": (txns_options, ["GET"]),
    "/h/accounts/validation": (validation, ["GET"]),
}
