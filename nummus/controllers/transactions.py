"""Transaction controllers."""

from __future__ import annotations

import datetime
import operator
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import exceptions as exc
from nummus import portfolio, utils
from nummus.controllers import common
from nummus.models import (
    Account,
    Asset,
    obj_session,
    query_count,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    update_rows_list,
    YIELD_PER,
)
from nummus.web import utils as web_utils

if TYPE_CHECKING:
    from typing_extensions import NotRequired

    from nummus.controllers.base import Routes

PAGE_LEN = 25


class _TxnContext(TypedDict):
    """Type definition for transaction context."""

    uri: str
    account: str
    account_uri: str
    # list[(account uri, name, option disabled)]
    accounts: list[tuple[str, str, bool]]
    cleared: bool
    date: datetime.date
    date_max: datetime.date
    amount: Decimal
    statement: str
    payee: str | None
    splits: list[_SplitContext]
    # list[(category uri, name, option disabled, group)]
    categories: list[tuple[str, str, bool, TransactionCategoryGroup]]
    payees: list[str]
    tags: list[str]
    similar_uri: str | None
    any_asset_splits: bool


class _SplitContext(TypedDict):
    """Type definition for transaction split context."""

    parent_uri: str
    category: str
    category_uri: str
    memo: str | None
    tag: str | None
    amount: Decimal | None

    asset_name: NotRequired[str | None]
    asset_ticker: NotRequired[str | None]
    asset_price: NotRequired[Decimal | None]
    asset_quantity: NotRequired[Decimal | None]


class _RowContext(_SplitContext):
    """Type definition for transaction row context."""

    date: datetime.date
    account: str
    payee: str | None
    category: str
    cleared: bool
    is_split: bool


def page_all() -> flask.Response:
    """GET /transactions.

    Returns:
        string HTML response
    """
    txn_table, title = ctx_table()
    return common.page(
        "transactions/page-all.jinja",
        title=title,
        ctx=txn_table,
        endpoint="transactions.table",
    )


def table() -> str | flask.Response:
    """GET /h/transactions/table.

    Returns:
        HTML response with url set
    """
    args = flask.request.args
    first_page = "page" not in args
    txn_table, title = ctx_table()
    html_title = f"<title>{title} - nummus</title>\n"
    html = html_title + flask.render_template(
        "transactions/table-rows.jinja",
        ctx=txn_table,
        endpoint="transactions.table",
        include_oob=first_page,
    )
    if not first_page:
        # Don't push URL for following pages
        return html
    response = flask.make_response(html)
    response.headers["HX-Push-URL"] = flask.url_for(
        "transactions.page_all",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **flask.request.args,
    )
    return response


def table_options() -> str:
    """GET /h/transactions/table-options.

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
        selected_account = args.get("account")
        selected_category = args.get("category")
        selected_period = args.get("period")
        selected_start = args.get("start")
        selected_end = args.get("end")

        query, _ = table_query(
            s,
            None,
            selected_account,
            selected_period,
            selected_start,
            selected_end,
            selected_category,
            uncleared=uncleared,
        )
        options = ctx_options(
            query,
            accounts,
            categories_emoji,
            selected_account,
            selected_category,
        )

        return flask.render_template(
            "transactions/table-filters.jinja",
            only_inner=True,
            endpoint="transactions.table",
            ctx={
                **options,
                "selected_period": selected_period,
                "selected_account": selected_account,
                "selected_category": selected_category,
                "uncleared": uncleared,
                "start": selected_start,
                "end": selected_end,
            },
        )


def new() -> str | flask.Response:
    """GET, PUT, & POST /h/transactions/new.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
    today = datetime.datetime.now().astimezone().date()

    with p.begin_session() as s:
        query = (
            s.query(Account)
            .with_entities(Account.id_, Account.name)
            .where(Account.closed.is_(False))
            .order_by(Account.name)
        )
        accounts: dict[int, str] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.emoji_name,
                TransactionCategory.asset_linked,
                TransactionCategory.group,
            )
            .order_by(TransactionCategory.group, TransactionCategory.name)
        )
        categories: dict[int, tuple[str, bool, TransactionCategoryGroup]] = {
            r[0]: (r[1], r[2], r[3]) for r in query.yield_per(YIELD_PER)
        }

        _, uncategorized_uri = TransactionCategory.uncategorized(s)

        query = s.query(Transaction.payee)
        payees = sorted(
            filter(None, (item for item, in query.distinct())),
            key=lambda item: item.lower(),
        )

        query = s.query(TransactionSplit.tag)
        tags = sorted(
            filter(None, (item for item, in query.distinct())),
            key=lambda item: item.lower(),
        )
        empty_split: _SplitContext = {
            "parent_uri": "",
            "category": "",
            "category_uri": uncategorized_uri,
            "memo": None,
            "tag": None,
            "amount": None,
        }
        ctx: _TxnContext = {
            "uri": "",
            "account": "",
            "account_uri": flask.request.args.get("account") or "",
            "accounts": [
                (Account.id_to_uri(acct_id), name, False)
                for acct_id, name in accounts.items()
            ],
            "cleared": False,
            "date": today,
            "date_max": today + datetime.timedelta(days=utils.DAYS_IN_WEEK),
            "amount": Decimal(0),
            "statement": "Manually created",
            "payee": None,
            "splits": [empty_split],
            "categories": [
                (TransactionCategory.id_to_uri(cat_id), *row)
                for cat_id, row in categories.items()
            ],
            "payees": payees,
            "tags": tags,
            "similar_uri": None,
            "any_asset_splits": False,
        }

        if flask.request.method == "GET":
            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx,
            )

        form = flask.request.form
        date = utils.parse_date(form.get("date"))
        amount = utils.evaluate_real_statement(form.get("amount"))
        account = form.get("account")
        payee = form.get("payee")

        split_memos = form.getlist("memo")
        split_categories = [
            TransactionCategory.uri_to_id(x) for x in form.getlist("category")
        ]
        split_tags = form.getlist("tag")
        split_amounts = [
            utils.evaluate_real_statement(x) for x in form.getlist("split-amount")
        ]
        if len(split_categories) == 1:
            split_amounts = [amount]

        if flask.request.method == "PUT":
            amount = amount or Decimal(0)
            ctx["account_uri"] = account or ""
            ctx["amount"] = amount
            ctx["payee"] = payee
            ctx["date"] = date or today

            splits: list[_SplitContext] = [
                {
                    "parent_uri": "",
                    "category": "",
                    "category_uri": TransactionCategory.id_to_uri(cat_id),
                    "memo": memo,
                    "tag": tag,
                    "amount": amount,
                }
                for cat_id, memo, tag, amount in zip(
                    split_categories,
                    split_memos,
                    split_tags,
                    split_amounts,
                    strict=True,
                )
                if amount
            ]

            split_sum = sum(filter(None, split_amounts)) or Decimal(0)

            remaining = amount - split_sum
            headline_error = (
                (
                    f"Sum of splits {utils.format_financial(split_sum)} "
                    f"not equal to total {utils.format_financial(amount)}. "
                    f"{utils.format_financial(remaining)} to assign"
                )
                if remaining != 0
                else ""
            )

            splits.extend(
                [empty_split] * 3,
            )
            ctx["splits"] = splits
            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx,
                headline_error=headline_error,
            )

        if date is None:
            return common.error("Transaction date must not be empty")
        if date > (today + datetime.timedelta(days=utils.DAYS_IN_WEEK)):
            return common.error("Date can only be up to 7 days in advance")
        if amount is None:
            return common.error("Transaction amount must not be empty")
        if account is None:
            return common.error("Transaction account must not be empty")

        try:
            with s.begin_nested():
                txn = Transaction(
                    account_id=Account.uri_to_id(account),
                    date=date,
                    amount=amount,
                    statement="Manually added",
                    payee=payee,
                )
                # Allow new with splits
                t_split = TransactionSplit(
                    parent=txn,
                    amount=split_amounts[0],
                    category_id=split_categories[0],
                    memo=split_memos[0],
                    tag=split_tags[0],
                )
                s.add_all((txn, t_split))
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(
            # account since transaction was created
            event="account",
            snackbar="Transaction created",
        )


def transaction(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/transactions/t/<uri>.

    Args:
        uri: URI of Transaction

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        txn = web_utils.find(s, Transaction, uri)

        if flask.request.method == "GET":
            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx_txn(txn),
            )
        if flask.request.method == "DELETE":
            if txn.cleared:
                return common.error("Cannot delete cleared transaction")
            date = datetime.date.fromordinal(txn.date_ord)
            s.query(TransactionSplit).where(
                TransactionSplit.parent_id == txn.id_,
            ).delete()
            s.delete(txn)
            return common.dialog_swap(
                # update-account since transaction was deleted
                event="account",
                snackbar=f"Transaction on {date} deleted",
            )

        try:
            amount_before = txn.amount
            with s.begin_nested():
                if err := _transaction_edit(s, txn):
                    return err
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(
            event="account" if txn.amount != amount_before else "transaction",
            snackbar="All changes saved",
        )


def _transaction_edit(s: orm.Session, txn: Transaction) -> str:
    """Edit transaction from form.

    Args:
        s: SQL session to use
        txn: Transaction to edit

    Returns:
        Error string or ""
    """
    today = datetime.datetime.now().astimezone().date()
    form = flask.request.form

    date = utils.parse_date(form.get("date"))
    if date is None:
        return common.error("Transaction date must not be empty")
    if date > (today + datetime.timedelta(days=utils.DAYS_IN_WEEK)):
        return common.error("Date can only be up to a week in the future")
    txn.date = date
    txn.payee = form.get("payee")

    if not txn.cleared:
        amount = utils.evaluate_real_statement(form.get("amount"))
        if amount is None:
            return common.error("Transaction amount must not be empty")
        txn.amount = amount
        acct_id = Account.uri_to_id(form["account"])
        txn.account_id = acct_id

    split_memos = form.getlist("memo")
    split_categories = [
        TransactionCategory.uri_to_id(x) for x in form.getlist("category")
    ]
    split_tags = form.getlist("tag")
    split_amounts = [
        utils.evaluate_real_statement(x) for x in form.getlist("split-amount")
    ]

    if len(split_categories) < 1:
        msg = "Transaction must have at least one split"
        return common.error(msg)
    if len(split_categories) == 1:
        split_amounts = [txn.amount]
    elif sum(filter(None, split_amounts)) != txn.amount:
        msg = "Non-zero remaining amount to be assigned"
        return common.error(msg)

    splits = [
        {
            "parent": txn,
            "category_id": cat_id,
            "memo": memo,
            "tag": tag,
            "amount": amount,
        }
        for cat_id, memo, tag, amount in zip(
            split_categories,
            split_memos,
            split_tags,
            split_amounts,
            strict=True,
        )
        if amount
    ]
    query = s.query(TransactionSplit).where(TransactionSplit.parent_id == txn.id_)
    update_rows_list(
        s,
        TransactionSplit,
        query,
        splits,
    )

    return ""


def split(uri: str) -> str:
    """PUT /h/transactions/<uri>/split.

    Args:
        uri: Transaction URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form

    with p.begin_session() as s:
        txn = web_utils.find(s, Transaction, uri)

        parent_amount = utils.parse_real(form["amount"]) or Decimal(0)
        account_id = Account.uri_to_id(form["account"])
        payee = form["payee"]
        date = utils.parse_date(form.get("date"))

        split_memos: list[str | None] = list(form.getlist("memo"))
        split_categories: list[str | None] = list(form.getlist("category"))
        split_tags: list[str | None] = list(form.getlist("tag"))
        split_amounts: list[Decimal | None] = [
            utils.evaluate_real_statement(x) for x in form.getlist("split-amount")
        ]
        if len(split_categories) == 1:
            split_amounts = [parent_amount]

        for _ in range(3):
            split_memos.append(None)
            split_categories.append(None)
            split_tags.append(None)
            split_amounts.append(None)

        _, uncategorized_uri = TransactionCategory.uncategorized(s)

        ctx_splits: list[_SplitContext] = []
        for memo, cat_uri, tag, amount in zip(
            split_memos,
            split_categories,
            split_tags,
            split_amounts,
            strict=True,
        ):
            item: _SplitContext = {
                "parent_uri": uri,
                "category": "",
                "category_uri": cat_uri or uncategorized_uri,
                "memo": memo,
                "tag": tag,
                "amount": amount,
                "asset_name": None,
                "asset_ticker": None,
                "asset_price": None,
                "asset_quantity": None,
            }
            ctx_splits.append(item)

        split_sum = sum(filter(None, split_amounts)) or Decimal(0)

        remaining = parent_amount - split_sum
        headline_error = (
            (
                f"Sum of splits {utils.format_financial(split_sum)} "
                f"not equal to total {utils.format_financial(parent_amount)}. "
                f"{utils.format_financial(remaining)} to assign"
            )
            if remaining != 0
            else ""
        )

        ctx = ctx_txn(
            txn,
            amount=parent_amount,
            account_id=account_id,
            payee=payee,
            date=date,
            splits=ctx_splits,
        )

        return flask.render_template(
            "transactions/edit.jinja",
            txn=ctx,
            headline_error=headline_error,
        )


def validation() -> str:
    """GET /h/transactions/validation.

    Returns:
        string HTML response
    """
    # dict{key: required}
    properties: dict[str, bool] = {
        "payee": True,
        "memo": False,
        "tag": False,
    }

    args = flask.request.args
    for key, required in properties.items():
        if key not in args:
            continue
        return web_utils.validate_string(
            args[key],
            is_required=required,
        )

    if "date" in args:
        return web_utils.validate_date(
            args["date"],
            is_required=True,
        )

    validate_splits = False
    if "split" in args:
        # Editing a split
        if r := web_utils.validate_real(args["split-amount"]):
            return r
        validate_splits = True
    elif "amount" in args:
        # Editing a split
        if r := web_utils.validate_real(
            args["amount"],
            is_required=True,
        ):
            return r
        validate_splits = True
    else:
        raise NotImplementedError

    if validate_splits:
        parent_amount = utils.evaluate_real_statement(args["amount"]) or Decimal(0)
        split_amounts = [
            utils.evaluate_real_statement(x) for x in args.getlist("split-amount")
        ]

        split_sum = sum(filter(None, split_amounts)) or Decimal(0)

        remaining = parent_amount - split_sum
        msg = (
            (
                f"Sum of splits {utils.format_financial(split_sum)} "
                f"not equal to total {utils.format_financial(parent_amount)}. "
                f"{utils.format_financial(remaining)} to assign"
            )
            if remaining != 0
            else ""
        )

        # Render sum of splits to headline since its a global error
        return flask.render_template(
            "shared/dialog-headline-error.jinja",
            oob=True,
            headline_error=msg,
        )

    raise NotImplementedError


def table_query(
    s: orm.Session,
    acct_uri: str | None = None,
    selected_account: str | None = None,
    selected_period: str | None = None,
    selected_start: str | None = None,
    selected_end: str | None = None,
    selected_category: str | None = None,
    *,
    uncleared: bool | None = False,
) -> tuple[orm.Query, bool]:
    """Create transactions table query.

    Args:
        s: SQL session to use
        acct_uri: Account URI to filter to
        selected_account: URI of account from args
        selected_period: Name of period from args
        selected_start: ISO date string of start from args
        selected_end: ISO date string of end from args
        selected_category: URI of category from args
        uncleared: True will only query uncleared transactions

    Returns:
        (SQL query, any_filters)
    """
    selected_account = acct_uri or selected_account
    query = s.query(TransactionSplit).order_by(
        TransactionSplit.date_ord.desc(),
        TransactionSplit.account_id,
        TransactionSplit.payee,
        TransactionSplit.category_id,
        TransactionSplit.tag,
        TransactionSplit.memo,
    )

    any_filters = False

    start = None
    end = None
    if selected_period and selected_period != "all":
        any_filters = True
        if selected_period == "custom":
            start = utils.parse_date(selected_start)
            end = utils.parse_date(selected_end)
        elif "-" in selected_period:
            start = datetime.date.fromisoformat(selected_period + "-01")
            end = utils.end_of_month(start)
        else:
            year = int(selected_period)
            start = datetime.date(year, 1, 1)
            end = datetime.date(year, 12, 31)

        if start:
            query = query.where(
                TransactionSplit.date_ord >= start.toordinal(),
            )
        if end:
            query = query.where(
                TransactionSplit.date_ord <= end.toordinal(),
            )

    if selected_account:
        any_filters |= acct_uri is None
        query = query.where(
            TransactionSplit.account_id == Account.uri_to_id(selected_account),
        )

    if selected_category:
        any_filters = True
        cat_id = TransactionCategory.uri_to_id(selected_category)
        query = query.where(TransactionSplit.category_id == cat_id)

    if uncleared:
        any_filters = True
        query = query.where(TransactionSplit.cleared.is_(False))

    return query, any_filters


def ctx_txn(
    txn: Transaction,
    *,
    amount: Decimal | None = None,
    account_id: int | None = None,
    payee: str | None = None,
    date: datetime.date | None = None,
    splits: list[_SplitContext] | None = None,
) -> _TxnContext:
    """Get the context to build the transaction edit dialog.

    Args:
        txn: Transaction to build context for
        amount: Override context amount
        account_id: Override context account
        payee: Override context payee
        date: Override context date
        splits: Override context splits

    Returns:
        Dictionary HTML context
    """
    s = obj_session(txn)

    account_id = txn.account_id if account_id is None else account_id

    query = s.query(Account).with_entities(
        Account.id_,
        Account.name,
        Account.closed,
    )
    accounts: dict[int, tuple[str, bool]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }
    query = (
        s.query(TransactionCategory)
        .with_entities(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
            TransactionCategory.asset_linked,
            TransactionCategory.group,
        )
        .order_by(TransactionCategory.group, TransactionCategory.name)
    )
    categories: dict[int, tuple[str, bool, TransactionCategoryGroup]] = {
        r[0]: (r[1], r[2], r[3]) for r in query.yield_per(YIELD_PER)
    }
    category_names = {cat_id: name for cat_id, (name, _, _) in categories.items()}
    query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
    assets: dict[int, tuple[str, str | None]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }

    ctx_splits: list[_SplitContext] = (
        [ctx_split(t_split, assets, category_names) for t_split in txn.splits]
        if splits is None
        else splits
    )
    any_asset_splits = any(split.get("asset_name") for split in ctx_splits)

    query = s.query(Transaction.payee)
    payees = sorted(
        filter(None, (item for item, in query.distinct())),
        key=lambda item: item.lower(),
    )

    query = s.query(TransactionSplit.tag)
    tags = sorted(
        filter(None, (item for item, in query.distinct())),
        key=lambda item: item.lower(),
    )

    # Run similar transaction
    similar_id = txn.find_similar(set_property=False)
    similar_uri = None if similar_id is None else Transaction.id_to_uri(similar_id)
    today = datetime.datetime.now().astimezone().date()
    return {
        "uri": txn.uri,
        "account": accounts[account_id][0],
        "account_uri": Account.id_to_uri(account_id),
        "accounts": [
            (Account.id_to_uri(acct_id), name, closed)
            for acct_id, (name, closed) in accounts.items()
        ],
        "cleared": txn.cleared,
        "date": datetime.date.fromordinal(txn.date_ord) if date is None else date,
        "date_max": today + datetime.timedelta(days=utils.DAYS_IN_WEEK),
        "amount": txn.amount if amount is None else amount,
        "statement": txn.statement,
        "payee": txn.payee if payee is None else payee,
        "splits": ctx_splits,
        "categories": [
            (TransactionCategory.id_to_uri(cat_id), *row)
            for cat_id, row in categories.items()
        ],
        "payees": payees,
        "tags": tags,
        "similar_uri": similar_uri,
        "any_asset_splits": any_asset_splits,
    }


def ctx_split(
    t_split: TransactionSplit,
    assets: dict[int, tuple[str, str | None]],
    categories: dict[int, str],
) -> _SplitContext:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        assets: Dict {id: (asset name, ticker)}
        categories: Account name mapping

    Returns:
        Dictionary HTML context
    """
    qty = t_split.asset_quantity or Decimal(0)
    if t_split.asset_id:
        asset_name, asset_ticker = assets[t_split.asset_id]
    else:
        asset_name = None
        asset_ticker = None
    return {
        "parent_uri": Transaction.id_to_uri(t_split.parent_id),
        "amount": t_split.amount,
        "category": categories[t_split.category_id],
        "category_uri": TransactionCategory.id_to_uri(t_split.category_id),
        "memo": t_split.memo,
        "tag": t_split.tag,
        "asset_name": asset_name,
        "asset_ticker": asset_ticker,
        "asset_price": abs(t_split.amount / qty) if qty else None,
        "asset_quantity": qty,
    }


def ctx_row(
    t_split: TransactionSplit,
    assets: dict[int, tuple[str, str | None]],
    accounts: dict[int, str],
    categories: dict[int, str],
    split_parents: set[int],
) -> _RowContext:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        assets: Dict {id: (asset name, ticker)}
        accounts: Account name mapping
        categories: Account name mapping
        split_parents: Set {Transaction.id_ that have more than 1 TransactionSplit}

    Returns:
        Dictionary HTML context
    """
    return {
        **ctx_split(t_split, assets, categories),
        "date": datetime.date.fromordinal(t_split.date_ord),
        "account": accounts[t_split.account_id],
        "payee": t_split.payee,
        "cleared": t_split.cleared,
        "is_split": t_split.parent_id in split_parents,
    }


def ctx_options(
    query: orm.Query,
    accounts: dict[int, str],
    categories: dict[int, str],
    selected_account: str | None = None,
    selected_category: str | None = None,
) -> dict[str, object]:
    """Get the context to build the options for table.

    Args:
        query: Query to use to get distinct values
        accounts: Account name mapping
        categories: Account name mapping
        selected_account: URI of account from args
        selected_category: URI of category from args

    Returns:
        List of HTML context
    """
    query = query.order_by(None)

    today = datetime.datetime.now().astimezone().date()
    month = utils.start_of_month(today)
    last_months = [utils.date_add_months(month, i) for i in range(0, -3, -1)]
    options_period = [
        ("All time", "all"),
        *((f"{m:%B}", m.isoformat()[:7]) for m in last_months),
        (str(month.year), str(month.year)),
        (str(month.year - 1), str(month.year - 1)),
        ("Custom date range", "custom"),
    ]

    query_options = query.with_entities(TransactionSplit.account_id).distinct()
    options_account = sorted(
        [
            (accounts[acct_id], Account.id_to_uri(acct_id))
            for acct_id, in query_options.yield_per(YIELD_PER)
        ],
        key=operator.itemgetter(0),
    )
    if len(options_account) == 0 and selected_account:
        acct_id = Account.uri_to_id(selected_account)
        options_account = [(accounts[acct_id], selected_account)]

    query_options = query.with_entities(TransactionSplit.category_id).distinct()
    options_category = sorted(
        [
            (
                categories[cat_id],
                TransactionCategory.id_to_uri(cat_id),
                utils.strip_emojis(categories[cat_id]),
            )
            for cat_id, in query_options.yield_per(YIELD_PER)
        ],
        key=operator.itemgetter(2),
    )
    if len(options_category) == 0 and selected_category:
        cat_id = TransactionCategory.uri_to_id(selected_category)
        options_category = [
            (categories[cat_id], selected_category, ""),
        ]

    return {
        "options_period": options_period,
        "options_account": options_account,
        "options_category": options_category,
    }


def ctx_table(acct_uri: str | None = None) -> tuple[dict[str, object], str]:
    """Get the context to build the transaction table.

    Args:
        acct_uri: Account uri to get transactions for, None will use filter queries

    Returns:
        tuple(Dictionary HTML context, page title)
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        accounts = Account.map_name(s)
        categories_emoji = TransactionCategory.map_name_emoji(s)
        categories = {
            cat_id: TransactionCategory.clean_emoji_name(name)
            for cat_id, name in categories_emoji.items()
        }
        query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
        assets: dict[int, tuple[str, str | None]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }

        args = flask.request.args
        search_str = args.get("search")
        uncleared = "uncleared" in args
        selected_account = args.get("account")
        selected_category = args.get("category")
        selected_period = args.get("period")
        selected_start = args.get("start")
        selected_end = args.get("end")

        page_start_str = args.get("page")
        if page_start_str is None:
            page_start = None
        else:
            try:
                page_start = int(page_start_str)
            except ValueError:
                page_start = datetime.date.fromisoformat(page_start_str).toordinal()

        query, any_filters = table_query(
            s,
            acct_uri,
            selected_account,
            selected_period,
            selected_start,
            selected_end,
            selected_category,
            uncleared=uncleared,
        )
        options = ctx_options(
            query,
            accounts,
            categories_emoji,
            selected_account,
            selected_category,
        )

        # Do search
        try:
            matches = TransactionSplit.search(query, search_str or "", categories)
        except exc.EmptySearchError:
            matches = None

        if matches is not None:
            any_filters = True
            query = query.where(TransactionSplit.id_.in_(matches))
            t_split_order = {t_split_id: i for i, t_split_id in enumerate(matches)}
        else:
            t_split_order = {}

        query_total = query.with_entities(func.sum(TransactionSplit.amount))

        if matches is not None:
            i_start = page_start or 0
            page = matches[i_start : i_start + PAGE_LEN]
            query = query.where(TransactionSplit.id_.in_(page))
            next_page = i_start + PAGE_LEN
        else:
            # Find the fewest dates to include that will make page at least
            # PAGE_LEN long
            included_date_ords: set[int] = set()
            query_page_count = query.with_entities(
                TransactionSplit.date_ord,
                func.count(),
            ).group_by(TransactionSplit.date_ord)
            if page_start:
                query_page_count = query_page_count.where(
                    TransactionSplit.date_ord <= page_start,
                )
            page_count = 0
            # Limit to PAGE_LEN since at most there is one txn per day
            for date_ord, count in query_page_count.limit(PAGE_LEN).yield_per(
                YIELD_PER,
            ):
                included_date_ords.add(date_ord)
                page_count += count
                if page_count >= PAGE_LEN:
                    break

            query = query.where(TransactionSplit.date_ord.in_(included_date_ords))

            next_page = (
                None
                if len(included_date_ords) == 0
                else datetime.date.fromordinal(min(included_date_ords) - 1)
            )

        n_matches = query_count(query)
        groups = _table_results(
            query,
            assets,
            accounts,
            categories_emoji,
            t_split_order,
        )
        title = _table_title(
            selected_period,
            selected_start,
            selected_end,
            selected_account and accounts[Account.uri_to_id(selected_account)],
            selected_category
            and categories_emoji[TransactionCategory.uri_to_id(selected_category)],
            uncleared=uncleared,
        )
        return {
            "uri": acct_uri,
            "transactions": groups,
            "query_total": query_total.scalar() or 0,
            "no_matches": n_matches == 0 and page_start is None,
            "next_page": None if n_matches < PAGE_LEN else next_page,
            "any_filters": any_filters,
            "search": search_str,
            **options,
            "selected_period": selected_period,
            "selected_account": selected_account,
            "selected_category": selected_category,
            "uncleared": uncleared,
            "start": selected_start,
            "end": selected_end,
        }, title


def _table_results(
    query: orm.Query[TransactionSplit],
    assets: dict[int, tuple[str, str | None]],
    accounts: dict[int, str],
    categories: dict[int, str],
    t_split_order: dict[int, int],
) -> list[tuple[datetime.date, list[_SplitContext]]]:
    """Get the table results from query.

    Args:
        query: TransactionSplit query for table
        assets: Dict {id: (asset name, ticker)}
        accounts: Account name mapping
        categories: Account name mapping
        t_split_order: Mapping of id_ to order if it matters

    Returns:
        TransactionSplits grouped by date
        list[(
            date,
            list[_SplitContext],
        )]
    """
    s = query.session

    # Iterate first to get required second querie
    t_splits: list[TransactionSplit] = []
    parent_ids: set[int] = set()
    for t_split in query.yield_per(YIELD_PER):
        t_splits.append(t_split)
        parent_ids.add(t_split.parent_id)

    # There are no more if there wasn't enough for a full page

    query_has_splits = (
        s.query(Transaction.id_)
        .join(TransactionSplit)
        .where(
            Transaction.id_.in_(parent_ids),
        )
        .group_by(Transaction.id_)
        .having(func.count() > 1)
    )
    has_splits = {r[0] for r in query_has_splits.yield_per(YIELD_PER)}

    t_splits_flat: list[tuple[_RowContext, int]] = []
    for t_split in t_splits:
        t_split_ctx = ctx_row(
            t_split,
            assets,
            accounts,
            categories,
            has_splits,
        )
        t_splits_flat.append(
            (t_split_ctx, t_split_order.get(t_split.id_, -t_split.date_ord)),
        )

    # sort by reverse date or search ranking
    t_splits_flat = sorted(t_splits_flat, key=operator.itemgetter(1))

    # Split by date boundaries but don't put dates together
    # since that messes up search ranking
    last_date: datetime.date | None = None
    groups: list[tuple[datetime.date, list[_SplitContext]]] = []
    current_group: list[_SplitContext] = []
    for t_split_ctx, _ in t_splits_flat:
        date = t_split_ctx["date"]
        if last_date and date != last_date:
            groups.append((last_date, current_group))
            current_group = []
        current_group.append(t_split_ctx)
        last_date = date
    if last_date and current_group:
        groups.append((last_date, current_group))

    return groups


def _table_title(
    period: str | None,
    start: str | None,
    end: str | None,
    account: str | None,
    category: str | None,
    *,
    uncleared: bool,
) -> str:
    """Create the table title.

    Args:
        period: Selected period
        start: Selected start date
        end: Selected stop date
        account: Selected account name
        category: Selected category name
        uncleared: Uncleared only or not

    Returns:
        Title string

    Raises:
        BadRequest: period is unknown
    """
    if len(flask.request.args) == 0:
        return "Transactions"
    if not period:
        title = ""
    elif period != "custom":
        title = period.title()
    elif start and end:
        title = f"{start} to {end}"
    elif start:
        title = f"from {start}"
    elif end:
        title = f"to {end}"
    else:  # pragma: no cover
        msg = "Invalid period option"
        raise exc.http.BadRequest(msg)
    title += " Transactions"

    if account:
        title += f", {account}"
    if category:
        title += f", {category}"
    if uncleared:
        title += ", Uncleared"
    return title


ROUTES: Routes = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (table, ["GET"]),
    "/h/transactions/table-options": (table_options, ["GET"]),
    "/h/transactions/new": (new, ["GET", "PUT", "POST"]),
    "/h/transactions/validation": (validation, ["GET"]),
    "/h/transactions/t/<path:uri>": (transaction, ["GET", "PUT", "DELETE"]),
    "/h/transactions/t/<path:uri>/split": (split, ["PUT"]),
}
