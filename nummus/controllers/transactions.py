"""Transaction controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from sqlalchemy import func, orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    Account,
    Asset,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus.controllers.base import Routes

PAGE_LEN = 25


class _SplitContext(TypedDict):
    """Type definition for transaction split context."""

    parent_uri: str
    uri: str
    date: datetime.date
    account: str
    payee: str | None
    memo: str | None
    category: str
    category_uri: str
    tag: str | None
    amount: Decimal
    locked: bool
    linked: bool
    asset_name: str | None
    asset_ticker: str | None
    asset_price: Decimal | None
    asset_quantity: Decimal
    is_split: bool


def page_all() -> flask.Response:
    """GET /transactions.

    Returns:
        string HTML response
    """
    txn_table = ctx_table()
    return common.page(
        "transactions/page-all.jinja",
        title="Transactions",
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
    txn_table = ctx_table()
    html = flask.render_template(
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
        unlinked = "unlinked" in args
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
            unlinked=unlinked,
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
            ctx={
                **options,
                "selected_period": selected_period,
                "selected_account": selected_account,
                "selected_category": selected_category,
                "unlinked": unlinked,
                "start": selected_start,
                "end": selected_end,
            },
        )


def new(acct_uri: str | None = None) -> str | flask.Response:
    """GET & POST /h/transactions/new.

    Args:
        acct_uri: Account uri to make transaction for, None for blank

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        query = (
            s.query(Account)
            .with_entities(Account.id_, Account.name)
            .where(Account.closed.is_(False))
        )
        if "budgeted" in flask.request.args:
            query = query.order_by(Account.budgeted.desc(), Account.name)
        else:
            query = query.order_by(Account.name)
        accounts: dict[int, str] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        query = s.query(TransactionCategory).with_entities(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
            TransactionCategory.asset_linked,
        )
        categories: dict[int, tuple[str, bool]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }

        if flask.request.method == "GET":
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
            ctx = {
                "uri": None,
                "account": acct_uri,
                "accounts": [
                    (Account.id_to_uri(acct_id), name)
                    for acct_id, name in accounts.items()
                ],
                "categories": [
                    (TransactionCategory.id_to_uri(cat_id), name, asset_linked)
                    for cat_id, (name, asset_linked) in categories.items()
                ],
                "payees": payees,
                "tags": tags,
                "date": datetime.date.today(),
                "amount": None,
                "splits": [{}],
            }

            return flask.render_template(
                "transactions/edit.jinja",
                txn=ctx,
            )

        form = flask.request.form
        date = utils.parse_date(form.get("date"))
        if date is None:
            return common.error("Transaction date must not be empty")
        if date > datetime.date.today():
            return common.error("Cannot create future transaction")
        amount = utils.evaluate_real_statement(form.get("amount"))
        if amount is None:
            return common.error("Transaction amount must not be empty")
        account = form.get("account")
        if account is None:
            return common.error("Transaction account must not be empty")
        payee = form.get("payee")

        split_memos = form.getlist("memo")
        split_categories = [
            TransactionCategory.uri_to_id(x) for x in form.getlist("category")
        ]
        split_tags = form.getlist("tag")
        split_amounts = [
            utils.evaluate_real_statement(x) for x in form.getlist("amount")
        ]
        if len(split_categories) == 1:
            split_amounts = [amount]

        try:
            with s.begin_nested():
                txn = Transaction(
                    account_id=Account.uri_to_id(account),
                    date=date,
                    amount=amount,
                    statement="Manually added",
                    payee=payee,
                    locked=False,
                    linked=False,
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

        return common.dialog_swap(event="update-transaction")


def transaction(uri: str, *, force_get: bool = False) -> str | flask.Response:
    """GET, PUT, & DELETE /h/transactions/t/<uri>.

    Args:
        uri: URI of Transaction or TransactionSplit
        force_get: True will force a GET request

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        try:
            parent = web_utils.find(s, Transaction, uri)
        except exc.http.BadRequest:
            child = web_utils.find(s, TransactionSplit, uri)
            parent = child.parent
        query = s.query(TransactionCategory).with_entities(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
            TransactionCategory.asset_linked,
        )
        categories: dict[int, tuple[str, bool]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }
        category_names = {k: v[0] for k, v in categories.items()}
        query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
        assets: dict[int, tuple[str, str | None]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }

        if force_get or flask.request.method == "GET":
            accounts = Account.map_name(s)

            splits = parent.splits

            ctx_splits: list[_SplitContext] = [
                ctx_split(
                    t_split,
                    accounts,
                    category_names,
                    assets,
                    set(),
                )
                for t_split in splits
            ]

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
            similar_id = p.find_similar_transaction(parent, set_property=False)
            similar_uri = similar_id and Transaction.id_to_uri(similar_id)

            ctx = {
                "uri": parent.uri,
                "account": Account.id_to_uri(parent.account_id),
                "accounts": [
                    (Account.id_to_uri(acct_id), name)
                    for acct_id, name in accounts.items()
                ],
                "locked": parent.locked,
                "linked": parent.linked,
                "date": datetime.date.fromordinal(parent.date_ord),
                "amount": parent.amount,
                "statement": parent.statement,
                "payee": parent.payee,
                "splits": ctx_splits,
                "categories": [
                    (TransactionCategory.id_to_uri(cat_id), name, asset_linked)
                    for cat_id, (name, asset_linked) in categories.items()
                ],
                "payees": payees,
                "tags": tags,
                "similar_uri": similar_uri,
            }

            return flask.render_template("transactions/edit.jinja", txn=ctx)
        if flask.request.method == "DELETE":
            if parent.linked:
                return common.error("Cannot delete linked transaction")
            s.query(TransactionSplit).where(
                TransactionSplit.parent_id == parent.id_,
            ).delete()
            s.delete(parent)
            return common.dialog_swap(event="update-transaction")

        try:
            with s.begin_nested():
                form = flask.request.form

                date = utils.parse_date(form.get("date"))
                if date is None:
                    return common.error("Transaction date must not be empty")
                parent.date = date
                parent.locked = "locked" in form
                parent.payee = form.get("payee")

                split_memos = form.getlist("memo")
                split_categories = [
                    TransactionCategory.uri_to_id(x) for x in form.getlist("category")
                ]
                split_tags = form.getlist("tag")
                split_amounts = [
                    utils.evaluate_real_statement(x) for x in form.getlist("amount")
                ]

                if len(split_categories) < 1:
                    msg = "Transaction must have at least one split"
                    return common.error(msg)
                if len(split_categories) == 1:
                    split_amounts = [parent.amount]
                elif sum(filter(None, split_amounts)) != parent.amount:
                    msg = "Non-zero remaining amount to be assigned"
                    return common.error(msg)

                splits = parent.splits

                # Add or remove splits to match desired
                n_add = len(split_categories) - len(splits)
                while n_add > 0:
                    splits.append(TransactionSplit())
                    n_add -= 1
                if n_add < 0:
                    for t_split in splits[n_add:]:
                        s.delete(t_split)
                    splits = splits[:n_add]

                # Update parent properties
                for t_split, memo, cat_id, tag, amount in zip(
                    splits,
                    split_memos,
                    split_categories,
                    split_tags,
                    split_amounts,
                    strict=True,
                ):
                    t_split.parent = parent

                    t_split.memo = memo
                    t_split.category_id = cat_id
                    t_split.tag = tag
                    if amount is None:
                        return common.error(
                            "Transaction split amount must not be empty",
                        )
                    t_split.amount = amount
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(event="update-transaction")


def split(uri: str) -> str:
    """GET, POST & DELETE /h/transactions/<uri>/split.

    Args:
        uri: Transaction URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        categories = TransactionCategory.map_name(s)

    form = flask.request.form

    payee: list[str | None] = list(form.getlist("payee"))
    memo: list[str | None] = list(form.getlist("memo"))
    category: list[str] = form.getlist("category")
    tag: list[str | None] = list(form.getlist("tag"))
    amount = [utils.evaluate_real_statement(x) for x in form.getlist("amount")]

    if flask.request.method == "POST":
        payee.append(None)
        memo.append(None)
        category.append("Uncategorized")
        tag.append(None)
        amount.append(None)
    elif flask.request.method == "GET":
        # Load all splits from similar transaction
        payee = []
        memo = []
        category = []
        tag = []
        amount = []

        with p.begin_session() as s:
            parent_id = Transaction.uri_to_id(flask.request.args["similar"])
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.payee,
                    TransactionSplit.memo,
                    TransactionSplit.category_id,
                    TransactionSplit.tag,
                    TransactionSplit.amount,
                )
                .where(TransactionSplit.parent_id == parent_id)
            )
            for t_payee, t_memo, t_cat_id, t_tag, t_amount in query.all():
                payee.append(t_payee)
                memo.append(t_memo)
                category.append(categories[t_cat_id])
                tag.append(t_tag)
                amount.append(t_amount)

            # Update the amount of the first split to be the proper sum
            parent = web_utils.find(s, Transaction, uri)
            amount[0] = parent.amount - sum(filter(None, amount[1:]))

    # DELETE below
    elif "all" in flask.request.args:
        payee = [None]
        memo = [None]
        category = ["Uncategorized"]
        tag = [None]
        amount = [None]
    elif len(payee) == 1:  # pragma: no cover
        # Delete button not available when only one split
        msg = "Transaction must have at least one split"
        raise ValueError(msg)
    else:
        i = int(flask.request.args["index"]) - 1

        payee.pop(i)
        memo.pop(i)
        category.pop(i)
        tag.pop(i)
        amount.pop(i)

    ctx_splits: list[dict[str, object]] = []
    for i in range(len(payee)):
        item = {
            "payee": payee[i],
            "memo": memo[i],
            "category": category[i],
            "tag": tag[i],
            "amount": amount[i],
        }
        ctx_splits.append(item)

    html = flask.render_template(
        "transactions/edit-splits.jinja",
        splits=ctx_splits,
        categories=categories.values(),
        parent={"uri": uri},
    )
    if flask.request.method in ["GET", "DELETE"]:
        with p.begin_session() as s:
            parent = web_utils.find(s, Transaction, uri)
            current = sum(filter(None, amount))
            html += flask.render_template(
                "transactions/edit-remaining.jinja",
                remaining=parent.amount - current,
                oob=True,
            )
    return html


def remaining(uri: str) -> str:
    """POST /h/transactions/<uri>/remaining.

    Args:
        uri: Transaction URI

    Returns:
      string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        parent = web_utils.find(s, Transaction, uri)
        form = flask.request.form

        amount = [utils.evaluate_real_statement(x) for x in form.getlist("amount")]
        current = sum(filter(None, amount))

        return flask.render_template(
            "transactions/edit-remaining.jinja",
            remaining=parent.amount - current,
        )


def table_query(
    s: orm.Session,
    acct: Account | None = None,
    selected_account: str | None = None,
    selected_period: str | None = None,
    selected_start: str | None = None,
    selected_end: str | None = None,
    selected_category: str | None = None,
    *,
    unlinked: bool | None = False,
) -> tuple[orm.Query, bool]:
    """Create transactions table query.

    Args:
        s: SQL session to use
        acct: Account to filter to
        selected_account: URI of account from args
        selected_period: Name of period from args
        selected_start: ISO date string of start from args
        selected_end: ISO date string of end from args
        selected_category: URI of category from args
        unlinked: True will only query unlinked transactions

    Returns:
        (SQL query, any_filters)
    """
    selected_account = (acct and acct.uri) or selected_account
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
        any_filters |= acct is None
        query = query.where(
            TransactionSplit.account_id == Account.uri_to_id(selected_account),
        )

    if selected_category:
        any_filters = True
        cat_id = TransactionCategory.uri_to_id(selected_category)
        query = query.where(TransactionSplit.category_id == cat_id)

    if unlinked:
        any_filters = True
        query = query.where(TransactionSplit.linked.is_(False))

    return query, any_filters


def ctx_split(
    t_split: TransactionSplit,
    accounts: dict[int, str],
    categories: dict[int, str],
    assets: dict[int, tuple[str, str | None]],
    split_parents: set[int],
) -> _SplitContext:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        accounts: Dict {id: account name}
        categories: Dict {id: category name}
        assets: Dict {id: (asset name, ticker)}
        split_parents: Set {Transaction.id_ that have more than 1 TransactionSplit}

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
        "uri": t_split.uri,
        "date": datetime.date.fromordinal(t_split.date_ord),
        "account": accounts[t_split.account_id],
        "payee": t_split.payee,
        "memo": t_split.memo,
        "category": categories[t_split.category_id],
        "category_uri": TransactionCategory.id_to_uri(t_split.category_id),
        "tag": t_split.tag,
        "amount": t_split.amount,
        "locked": t_split.locked,
        "linked": t_split.linked,
        "asset_name": asset_name,
        "asset_ticker": asset_ticker,
        "asset_price": abs(t_split.amount / qty) if qty else None,
        "asset_quantity": qty,
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

    today = datetime.date.today()
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
        key=lambda item: item[0],
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
        key=lambda item: item[2],
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


def ctx_table(
    acct: Account | None = None,
) -> dict[str, object]:
    """Get the context to build the transaction table.

    Args:
        acct: Account to get transactions for, None will use filter queries

    Returns:
        Dictionary HTML context
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
        unlinked = "unlinked" in args
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
            acct,
            selected_account,
            selected_period,
            selected_start,
            selected_end,
            selected_category,
            unlinked=unlinked,
        )
        options = ctx_options(
            query,
            accounts,
            categories_emoji,
            selected_account,
            selected_category,
        )

        # Do search
        matches = (
            TransactionSplit.search(query, search_str, categories)
            if search_str
            else None
        )
        if matches is not None:
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
                if page_count > PAGE_LEN:
                    break

            query = query.where(TransactionSplit.date_ord.in_(included_date_ords))

            next_page = datetime.date.fromordinal(min(included_date_ords) - 1)

        # Iterate first to get required second queries
        t_splits: list[TransactionSplit] = []
        parent_ids: set[int] = set()
        for t_split in query.yield_per(YIELD_PER):
            t_splits.append(t_split)
            parent_ids.add(t_split.parent_id)

        # There are no more if there wasn't enough for a full page
        no_more = len(t_splits) < PAGE_LEN

        query = (
            s.query(Transaction.id_)
            .join(TransactionSplit)
            .where(
                Transaction.id_.in_(parent_ids),
            )
            .group_by(Transaction.id_)
            .having(func.count() > 1)
        )
        has_splits = {r[0] for r in query.yield_per(YIELD_PER)}

        t_splits_flat: list[tuple[_SplitContext, int]] = []
        for t_split in t_splits:
            t_split_ctx = ctx_split(
                t_split,
                accounts,
                categories_emoji,
                assets,
                has_splits,
            )
            t_splits_flat.append(
                (t_split_ctx, t_split_order.get(t_split.id_, -t_split.date_ord)),
            )

        # sort by reverse date or search ranking
        t_splits_flat = sorted(t_splits_flat, key=lambda item: item[1])

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

        return {
            "uri": None if acct is None else acct.uri,
            "transactions": groups,
            "query_total": query_total.scalar() or 0,
            "no_matches": len(t_splits_flat) == 0 and page_start is None,
            "next_page": None if no_more else next_page,
            "any_filters": any_filters,
            "search": search_str,
            **options,
            "selected_period": selected_period,
            "selected_account": selected_account,
            "selected_category": selected_category,
            "unlinked": unlinked,
            "start": selected_start,
            "end": selected_end,
        }


ROUTES: Routes = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (table, ["GET"]),
    "/h/transactions/table-options": (table_options, ["GET"]),
    "/h/transactions/new": (new, ["GET", "POST"]),
    "/h/transactions/t/<path:uri>": (transaction, ["GET", "PUT", "DELETE"]),
    "/h/transactions/t/<path:uri>/split": (split, ["GET", "POST", "DELETE"]),
    "/h/transactions/t/<path:uri>/remaining": (remaining, ["POST"]),
}
