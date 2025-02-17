"""Transaction controllers."""

from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
from rapidfuzz import process
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


class _OptionContex(TypedDict):
    """Type definition for option context."""

    name: str
    label: str
    name_clean: str
    checked: bool
    hidden: bool
    score: int


class _SplitContext(TypedDict):
    """Type definition for transaction split context."""

    parent_uri: str
    uri: str
    date: datetime.date
    account: str
    payee: str | None
    description: str | None
    category: str
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


def table_options(field: str) -> str:
    """GET /h/transactions/options/<field>.

    Args:
        field: Name of field to get options for

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        args = flask.request.args

        id_mapping = None
        label_mapping = None
        if field == "account":
            id_mapping = Account.map_name(s)
        elif field == "category":
            id_mapping = TransactionCategory.map_name(s)
            label_mapping = TransactionCategory.map_name_emoji(s)
        elif field not in {"payee", "tag"}:
            msg = f"Unexpected txns options: {field}"
            raise exc.http.BadRequest(msg)

        query, _, _, _ = table_unfiltered_query(s)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "transactions/table-options.jinja",
            options=ctx_options(
                query,
                field,
                id_mapping,
                label_mapping=label_mapping,
                search_str=search_str,
            ),
            name=field,
            search_str=search_str,
            endpoint="transactions.table",
            endpoint_new="transactions.new",
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
            query = query.where(Account.budgeted)
        accounts: dict[int, str] = dict(query.yield_per(YIELD_PER))  # type: ignore[attr-defined]

        if flask.request.method == "GET":
            ctx_parent = {
                "uri": None,
                "account": (
                    None if acct_uri is None else accounts[Account.uri_to_id(acct_uri)]
                ),
                "date": datetime.date.today(),
                "amount": None,
                "statement": "",
            }

            return flask.render_template(
                "transactions/new.jinja",
                parent=ctx_parent,
                accounts=accounts.values(),
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
        statement = form.get("statement")

        # Reverse accounts for LUT
        accounts_rev = {v: k for k, v in accounts.items()}

        category_id: int | None = (
            s.query(TransactionCategory.id_)
            .where(TransactionCategory.name == "Uncategorized")
            .scalar()
        )
        if category_id is None:  # pragma: no cover
            msg = "Category Uncategorized not found"
            raise exc.ProtectedObjectNotFoundError(msg)

        try:
            with s.begin_nested():
                txn = Transaction(
                    account_id=accounts_rev[account],
                    date=date,
                    amount=amount,
                    statement=statement or "Manually added",
                    locked=False,
                    linked=False,
                )
                t_split = TransactionSplit(
                    parent=txn,
                    amount=amount,
                    category_id=category_id,
                )
                s.add_all((txn, t_split))
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        uri = txn.uri

        edit_overlay = transaction(uri, force_get=True)
        if not isinstance(edit_overlay, str):  # pragma: no cover
            msg = "Edit overlay did not return a string"
            raise TypeError(msg)
        # Adding transactions update account cause the balance changes
        return common.dialog_swap(edit_overlay, event="update-account")


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
        categories = TransactionCategory.map_name(s, no_asset_linked=True)
        query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
        assets: dict[int, tuple[str, str | None]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }

        if force_get or flask.request.method == "GET":
            accounts = Account.map_name(s)

            ctx_parent = {
                "uri": parent.uri,
                "account": accounts[parent.account_id],
                "locked": parent.locked,
                "linked": parent.linked,
                "date": datetime.date.fromordinal(parent.date_ord),
                "amount": parent.amount,
                "statement": parent.statement,
            }

            splits = parent.splits

            ctx_splits: list[_SplitContext] = [
                ctx_split(t_split, accounts, categories, assets, {parent.id_})
                for t_split in splits
            ]

            query = s.query(TransactionSplit.payee).where(
                TransactionSplit.asset_id.is_(None),
            )
            payees = sorted(
                filter(None, (item for item, in query.distinct())),
                key=lambda item: item.lower(),
            )

            query = s.query(TransactionSplit.tag).where(
                TransactionSplit.asset_id.is_(None),
            )
            tags = sorted(
                filter(None, (item for item, in query.distinct())),
                key=lambda item: item.lower(),
            )

            # Run transaction
            similar_id = p.find_similar_transaction(parent, set_property=False)
            similar_uri = similar_id and Transaction.id_to_uri(similar_id)

            return flask.render_template(
                "transactions/edit.jinja",
                splits=ctx_splits,
                parent=ctx_parent,
                payees=payees,
                categories=categories.values(),
                tags=tags,
                similar_uri=similar_uri,
            )
        if flask.request.method == "DELETE":
            if parent.linked:
                return common.error("Cannot delete linked transaction")
            s.query(TransactionSplit).where(
                TransactionSplit.parent_id == parent.id_,
            ).delete()
            s.delete(parent)
            # Adding transactions update account cause the balance changes
            return common.dialog_swap(event="update-account")

        try:
            with s.begin_nested():
                form = flask.request.form

                date = utils.parse_date(form.get("date"))
                if date is None:
                    return common.error("Transaction date must not be empty")
                parent.date = date
                parent.locked = "locked" in form

                payee = form.getlist("payee")
                description = form.getlist("description")
                category = form.getlist("category")
                tag = form.getlist("tag")
                amount = [
                    utils.evaluate_real_statement(x) for x in form.getlist("amount")
                ]

                if sum(filter(None, amount)) != parent.amount:
                    msg = "Non-zero remaining amount to be assigned"
                    return common.error(msg)

                if len(payee) < 1:
                    msg = "Transaction must have at least one split"
                    return common.error(msg)

                splits = parent.splits

                # Add or remove splits to match desired
                n_add = len(payee) - len(splits)
                while n_add > 0:
                    splits.append(TransactionSplit())
                    n_add -= 1
                if n_add < 0:
                    for t_split in splits[n_add:]:
                        s.delete(t_split)
                    splits = splits[:n_add]

                # Reverse categories for LUT
                categories_rev = {v: k for k, v in categories.items()}

                # Update parent properties
                for i, t_split in enumerate(splits):
                    t_split.parent = parent

                    try:
                        t_split.payee = payee[i]
                        t_split.description = description[i]
                        t_split.category_id = categories_rev[category[i]]
                        t_split.tag = tag[i]
                        a = amount[i]
                    except IndexError:
                        return common.error("Transaction split missing properties")
                    if a is None:
                        return common.error(
                            "Transaction split amount must not be empty",
                        )
                    t_split.amount = a
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
    description: list[str | None] = list(form.getlist("description"))
    category: list[str] = form.getlist("category")
    tag: list[str | None] = list(form.getlist("tag"))
    amount = [utils.evaluate_real_statement(x) for x in form.getlist("amount")]

    if flask.request.method == "POST":
        payee.append(None)
        description.append(None)
        category.append("Uncategorized")
        tag.append(None)
        amount.append(None)
    elif flask.request.method == "GET":
        # Load all splits from similar transaction
        payee = []
        description = []
        category = []
        tag = []
        amount = []

        with p.begin_session() as s:
            parent_id = Transaction.uri_to_id(flask.request.args["similar"])
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.payee,
                    TransactionSplit.description,
                    TransactionSplit.category_id,
                    TransactionSplit.tag,
                    TransactionSplit.amount,
                )
                .where(TransactionSplit.parent_id == parent_id)
            )
            for t_payee, t_desc, t_cat_id, t_tag, t_amount in query.all():
                payee.append(t_payee)
                description.append(t_desc)
                category.append(categories[t_cat_id])
                tag.append(t_tag)
                amount.append(t_amount)

            # Update the amount of the first split to be the proper sum
            parent = web_utils.find(s, Transaction, uri)
            amount[0] = parent.amount - sum(filter(None, amount[1:]))

    # DELETE below
    elif "all" in flask.request.args:
        payee = [None]
        description = [None]
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
        description.pop(i)
        category.pop(i)
        tag.pop(i)
        amount.pop(i)

    ctx_splits: list[dict[str, object]] = []
    for i in range(len(payee)):
        item = {
            "payee": payee[i],
            "description": description[i],
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
        "description": t_split.description,
        "category": categories[t_split.category_id],
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
    field: str,
    id_mapping: dict[int, str] | None = None,
    label_mapping: dict[int, str] | None = None,
    search_str: str | None = None,
) -> list[_OptionContex]:
    """Get the context to build the options for table.

    Args:
        query: Query to use to get distinct values
        field: TransactionSplit field to get options for
        id_mapping: Item ID to name mapping
        label_mapping: Item ID to label mapping, None will use id_mapping
        search_str: Search options and hide non-matches

    Returns:
        List of HTML context
    """
    query = query.order_by(None)
    args = flask.request.args
    selected: list[str] = args.getlist(field)
    options_: list[_OptionContex] = []
    entities = {
        "account": TransactionSplit.account_id,
        "payee": TransactionSplit.payee,
        "category": TransactionSplit.category_id,
        "tag": TransactionSplit.tag,
        "asset": TransactionSplit.asset_id,
    }
    for (id_,) in query.with_entities(entities[field]).distinct():
        if id_ is None:
            continue
        name = id_mapping[id_] if id_mapping else id_
        label = label_mapping[id_] if label_mapping else name
        name_clean = utils.strip_emojis(name).lower()
        item: _OptionContex = {
            "name": name,
            "label": label,
            "name_clean": name_clean,
            "checked": name in selected,
            "hidden": False,
            "score": 0,
        }
        options_.append(item)
    if search_str not in [None, ""]:
        names = {i: item["name_clean"] for i, item in enumerate(options_)}
        extracted = process.extract(
            search_str,
            names,
            limit=None,
        )
        for _, score, i in extracted:
            options_[i]["score"] = int(score)
            options_[i]["hidden"] = score < utils.SEARCH_THRESHOLD
    if field in ["payee", "tag"]:
        name = "[blank]"
        item = {
            "name": name,
            "label": name,
            "name_clean": name,
            "checked": name in selected,
            "hidden": search_str not in [None, ""],
            "score": 100,
        }
        options_.append(item)

    return sorted(
        options_,
        key=lambda item: (-item["score"], not item["checked"], item["name_clean"]),
    )


def table_unfiltered_query(
    s: orm.Session,
    acct: Account | None = None,
) -> orm.Query:
    """Create transactions table query without any column filters.

    Args:
        s: SQL session to use
        acct: Account to get transactions for, None will use filter queries

    Returns:
        SQL query
    """
    query = s.query(TransactionSplit).order_by(
        TransactionSplit.date_ord.desc(),
        TransactionSplit.account_id,
        TransactionSplit.payee,
        TransactionSplit.category_id,
        TransactionSplit.tag,
        TransactionSplit.description,
    )
    if acct is not None:
        query = query.where(TransactionSplit.account_id == acct.id_)

    return query


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

    today = datetime.date.today()
    month = utils.start_of_month(today)

    with p.begin_session() as s:
        args = flask.request.args
        unlinked = "unlinked" in args
        selected_account = (acct and acct.uri) or args.get("account")
        selected_category = args.get("category")
        selected_period = args.get("period")

        page_start_str = args.get("page")
        page_start_ord = (
            None
            if page_start_str is None
            else datetime.date.fromisoformat(page_start_str).toordinal()
        )

        accounts = Account.map_name(s)
        categories_emoji = TransactionCategory.map_name_emoji(s)
        query = s.query(Asset).with_entities(Asset.id_, Asset.name, Asset.ticker)
        assets: dict[int, tuple[str, str | None]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }

        query = s.query(TransactionSplit).order_by(
            TransactionSplit.date_ord.desc(),
            TransactionSplit.account_id,
            TransactionSplit.payee,
            TransactionSplit.category_id,
            TransactionSplit.tag,
            TransactionSplit.description,
        )

        any_filters = False

        # TODO (WattsUp): Update filter options as they are selected
        start = None
        end = None
        if selected_period and selected_period != "all":
            any_filters = True
            if selected_period == "custom":
                start = utils.parse_date(args.get("start"))
                end = utils.parse_date(args.get("end"))
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
                    utils.strip_emojis(categories_emoji[cat_id]),
                    TransactionCategory.id_to_uri(cat_id),
                )
                for cat_id, in query_options.yield_per(YIELD_PER)
            ],
            key=lambda item: item[0],
        )
        if len(options_category) == 0 and selected_category:
            cat_id = TransactionCategory.uri_to_id(selected_category)
            options_category = [
                (utils.strip_emojis(categories_emoji[cat_id]), selected_category),
            ]

        query_total = query.with_entities(func.sum(TransactionSplit.amount))

        # Find the fewest dates to include that will make page at least PAGE_LEN long
        included_date_ords: set[int] = set()
        query_page_count = query.with_entities(
            TransactionSplit.date_ord,
            func.count(),
        ).group_by(TransactionSplit.date_ord)
        if page_start_ord:
            query_page_count = query_page_count.where(
                TransactionSplit.date_ord <= page_start_ord,
            )
        page_count = 0
        # Limit to PAGE_LEN since at most there is one txn per day
        for date_ord, count in query_page_count.limit(PAGE_LEN).yield_per(YIELD_PER):
            included_date_ords.add(date_ord)
            page_count += count
            if page_count > PAGE_LEN:
                break

        query = query.where(TransactionSplit.date_ord.in_(included_date_ords))

        # Iterate first to get required second queries
        # 37ms without
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

        t_splits_ctx: dict[datetime.date, list[_SplitContext]] = defaultdict(list)
        for t_split in t_splits:
            t_split_ctx = ctx_split(
                t_split,
                accounts,
                categories_emoji,
                assets,
                has_splits,
            )
            t_splits_ctx[t_split_ctx["date"]].append(t_split_ctx)

        return {
            "uri": None if acct is None else acct.uri,
            "transactions": t_splits_ctx,
            "query_total": query_total.scalar() or 0,
            "no_matches": len(t_splits_ctx) == 0 and page_start_ord is None,
            "next_page": (
                None
                if no_more
                else datetime.date.fromordinal(min(included_date_ords) - 1)
            ),
            "any_filters": any_filters,
            "options_period": options_period,
            "options_account": options_account,
            "options_category": options_category,
            "selected_period": selected_period,
            "selected_account": selected_account,
            "selected_category": selected_category,
            "unlinked": unlinked,
            "start": start,
            "end": end,
        }


ROUTES: Routes = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (table, ["GET"]),
    "/h/transactions/table-options/<path:field>": (table_options, ["GET"]),
    "/h/transactions/new": (new, ["GET", "POST"]),
    "/h/transactions/t/<path:uri>": (transaction, ["GET", "PUT", "DELETE"]),
    "/h/transactions/t/<path:uri>/split": (split, ["GET", "POST", "DELETE"]),
    "/h/transactions/t/<path:uri>/remaining": (remaining, ["POST"]),
}
