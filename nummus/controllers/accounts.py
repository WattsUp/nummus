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
        return common.page(
            "accounts/page.jinja",
            title=title,
            acct=ctx_account(acct),
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
                acct=ctx_account(acct),
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


def ctx_account(acct: Account, *, skip_today: bool = False) -> _AccountContext:
    """Get the context to build the account details.

    Args:
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
        s = orm.object_session(acct)
        if s is None:
            raise exc.UnboundExecutionError
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
    }


def ctx_assets(s: orm.Session, acct: Account) -> dict[str, object] | None:
    """Get the context to build the account assets.

    Args:
        s: SQL session to use
        acct: Account to generate context for

    Returns:
        Dictionary HTML context
    """
    raise NotImplementedError
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
            accounts[acct.id_] = ctx_account(acct, skip_today=True)
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
    "/h/accounts/a/<path:uri>/validation": (validation, ["GET"]),
    "/h/accounts/a/<path:uri>/txns": (txns, ["GET"]),
    "/h/accounts/a/<path:uri>/txns-options": (txns_options, ["GET"]),
}
