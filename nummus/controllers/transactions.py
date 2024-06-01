"""Transaction controllers."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

import flask
import sqlalchemy
from rapidfuzz import process
from sqlalchemy import orm

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    Account,
    paginate,
    search,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


class _OptionContex(TypedDict):
    """Type definition for option context."""

    name: str
    checked: bool
    hidden: bool
    score: int


def page_all() -> str:
    """GET /transactions.

    Returns:
        string HTML response
    """
    txn_table, title = ctx_table()
    return common.page(
        "transactions/index-content.jinja",
        title=title,
        txn_table=txn_table,
        controller="transactions",
    )


def table() -> flask.Response:
    """GET /h/transactions/table.

    Returns:
        HTML response with url set
    """
    txn_table, title = ctx_table()
    html_title = f"<title>{title}</title>\n"
    html = html_title + flask.render_template(
        "transactions/table.jinja",
        txn_table=txn_table,
        include_oob=True,
        controller="transactions",
    )
    response = flask.make_response(html)
    args = dict(flask.request.args)
    response.headers["HX-Push-Url"] = flask.url_for(
        "transactions.page_all",
        _external=False,
        **args,
    )
    return response


def options(field: str) -> str:
    """GET /h/transactions/options/<field>.

    Args:
        field: Name of field to get options for

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        args = flask.request.args

        id_mapping = None
        if field == "account":
            id_mapping = Account.map_name(s)
        elif field == "category":
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
        )
        if start is not None:
            start_ord = start.toordinal()
            query = query.where(TransactionSplit.date_ord >= start_ord)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "transactions/table-options.jinja",
            options=ctx_options(query, field, id_mapping, search_str=search_str),
            name=field,
            search_str=search_str,
            controller="transactions",
        )


def ctx_options(
    query: orm.Query,
    field: str,
    id_mapping: dict[int, str] | None = None,
    search_str: str | None = None,
) -> list[_OptionContex]:
    """Get the context to build the options for table.

    Args:
        query: Query to use to get distinct values
        field: TransactionSplit field to get options for
        id_mapping: Item ID to name mapping
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
    }
    for (id_,) in query.with_entities(entities[field]).distinct():
        if id_ is None:
            continue
        name = id_mapping[id_] if id_mapping else id_
        item: _OptionContex = {
            "name": name,
            "checked": name in selected,
            "hidden": False,
            "score": 0,
        }
        options_.append(item)
    if search_str not in [None, ""]:
        names = {i: item["name"] for i, item in enumerate(options_)}
        extracted = process.extract(
            search_str,
            names,
            limit=None,
            processor=lambda s: s.lower(),
        )
        for _, score, i in extracted:
            options_[i]["score"] = int(score)
            options_[i]["hidden"] = score < utils.SEARCH_THRESHOLD
    if field in ["payee", "tag"]:
        name = "[blank]"
        item = {
            "name": name,
            "checked": name in selected,
            "hidden": search_str not in [None, ""],
            "score": 100,
        }
        options_.append(item)

    return sorted(
        options_,
        key=lambda item: (-item["score"], not item["checked"], item["name"].lower()),
    )


def ctx_table(
    acct: Account | None = None,
    default_period: str = "this-month",
) -> tuple[dict[str, object], str]:
    """Get the context to build the transaction table.

    Args:
        acct: Account to get transactions for, None will use filter queries
        default_period: Default period to use if no period given

    Returns:
        Dictionary HTML context, title of page
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        args = flask.request.args

        accounts = Account.map_name(s)
        categories = TransactionCategory.map_name(s)

        period = args.get("period", default_period)
        start, end = web_utils.parse_period(
            period,
            args.get("start", type=datetime.date.fromisoformat),
            args.get("end", type=datetime.date.fromisoformat),
        )
        if start is None and acct is not None:
            opened_on_ord = acct.opened_on_ord
            start = (
                end
                if opened_on_ord is None
                else datetime.date.fromordinal(opened_on_ord)
            )
        end_ord = end.toordinal()
        search_str = args.get("search", "").strip()
        locked = args.get("locked", type=utils.parse_bool)

        page_len = 25
        offset = int(args.get("offset", 0))
        page_total = Decimal(0)

        query = (
            s.query(TransactionSplit)
            .where(
                TransactionSplit.asset_id.is_(None),
                TransactionSplit.date_ord <= end_ord,
            )
            .order_by(TransactionSplit.date_ord)
        )
        if start is not None:
            start_ord = start.toordinal()
            query = query.where(TransactionSplit.date_ord >= start_ord)
        if acct is not None:
            query = query.where(TransactionSplit.account_id == acct.id_)

        # Get options with these filters
        options_account = ctx_options(query, "account", accounts)
        options_payee = ctx_options(query, "payee")
        options_category = ctx_options(query, "category", categories)
        options_tag = ctx_options(query, "tag")

        def merge(options: list[_OptionContex], selected: list[str]) -> list[str]:
            options_flat = [option["name"] for option in options]
            return [item for item in selected if item in options_flat]

        selected_accounts = merge(options_account, args.getlist("account"))
        selected_payees = merge(options_payee, args.getlist("payee"))
        selected_categories = merge(options_category, args.getlist("category"))
        selected_tags = merge(options_tag, args.getlist("tag"))

        if acct is None and len(selected_accounts) != 0:
            ids = [
                acct_id
                for acct_id, name in accounts.items()
                if name in selected_accounts
            ]
            query = query.where(TransactionSplit.account_id.in_(ids))

        if len(selected_payees) != 0:
            try:
                selected_payees.remove("[blank]")
                query = query.where(
                    TransactionSplit.payee.in_(selected_payees)
                    | TransactionSplit.payee.is_(None),
                )
            except ValueError:
                query = query.where(TransactionSplit.payee.in_(selected_payees))

        if len(selected_categories) != 0:
            ids = [
                cat_id
                for cat_id, name in categories.items()
                if name in selected_categories
            ]
            query = query.where(TransactionSplit.category_id.in_(ids))

        if len(selected_tags) != 0:
            try:
                selected_tags.remove("[blank]")
                query = query.where(
                    TransactionSplit.tag.in_(selected_tags)
                    | TransactionSplit.tag.is_(None),
                )
            except ValueError:
                query = query.where(TransactionSplit.tag.in_(selected_tags))

        if locked is not None:
            query = query.where(TransactionSplit.locked == locked)

        if search_str != "":
            query = search(query, TransactionSplit, search_str)  # type: ignore[attr-defined]

        page, count, offset_next = paginate(query, page_len, offset)  # type: ignore[attr-defined]

        query = query.with_entities(sqlalchemy.func.sum(TransactionSplit.amount))
        query_total = query.scalar() or Decimal(0)

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

        transactions: list[dict[str, object]] = []
        for t_split in page:  # type: ignore[attr-defined]
            t_split: TransactionSplit
            t_split_ctx = ctx_split(t_split, accounts, categories)
            page_total += t_split.amount

            transactions.append(t_split_ctx)

        offset_last = max(0, int((count - 1) // page_len) * page_len)

        if period == "custom":
            title = f"{start} to {end}"
        else:
            title = period.replace("-", " ").title()
        # Add filter if used
        filters = [
            *selected_accounts,
            *selected_payees,
            *selected_categories,
            *selected_tags,
        ]
        if locked is not None:
            filters.append("Locked" if locked else "Unlocked")
        if search_str:
            filters.append(f'"{search_str}"')
        n_filters = len(filters)
        if n_filters > 0:
            n_included = 2
            title += ", " + ", ".join(filters[:n_included])
            if n_filters > n_included:
                title += f", & {n_filters-n_included} Filters"

        title = f"Transactions {title} | nummus"

        return {
            "uri": None if acct is None else acct.uri,
            "transactions": transactions,
            "count": count,
            "offset": offset,
            "i_first": 0 if count == 0 else offset + 1,
            "i_last": min(offset + page_len, count),
            "page_len": page_len,
            "page_total": page_total,
            "query_total": query_total,
            "offset_first": 0,
            "offset_prev": max(0, offset - page_len),
            "offset_next": offset_next or offset_last,
            "offset_last": offset_last,
            "start": start,
            "end": end,
            "period": period,
            "search": search_str,
            "locked": locked,
            "options-account": options_account,
            "options-payee": options_payee,
            "options-category": options_category,
            "options-tag": options_tag,
            "any-filters-account": len(selected_accounts) > 0,
            "any-filters-payee": len(selected_payees) > 0,
            "any-filters-category": len(selected_categories) > 0,
            "any-filters-tag": len(selected_tags) > 0,
        }, title


def ctx_split(
    t_split: TransactionSplit,
    accounts: dict[int, str],
    categories: dict[int, str],
) -> dict[str, object]:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        accounts: Dict {id: account name}
        categories: Dict {id: category name}

    Returns:
        Dictionary HTML context
    """
    return {
        "uri": t_split.uri,
        "date": datetime.date.fromordinal(t_split.date_ord),
        "account": accounts[t_split.account_id],
        "payee": t_split.payee,
        "description": t_split.description,
        "category": categories[t_split.category_id],
        "tag": t_split.tag,
        "amount": t_split.amount,
        "locked": t_split.locked,
    }


def edit(uri: str) -> str | flask.Response:
    """GET & POST /h/transactions/t/<uri>/edit.

    Args:
        uri: URI of Transaction or TransactionSplit

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        try:
            parent: Transaction = web_utils.find(s, Transaction, uri)  # type: ignore[attr-defined]
        except exc.http.BadRequest:
            child: TransactionSplit = web_utils.find(s, TransactionSplit, uri)  # type: ignore[attr-defined]
            parent = child.parent
        categories = TransactionCategory.map_name(s)

        if flask.request.method == "GET":
            accounts = Account.map_name(s)

            ctx_parent = {
                "uri": parent.uri,
                "account": accounts[parent.account_id],
                "locked": parent.locked,
                "date": datetime.date.fromordinal(parent.date_ord),
                "amount": parent.amount,
                "statement": parent.statement,
            }

            splits = parent.splits

            ctx_splits: list[dict[str, object]] = [
                ctx_split(t_split, accounts, categories) for t_split in splits
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
            similar_id = p.find_similar_transaction(parent, do_commit=False)
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

        try:
            form = flask.request.form

            date = form.get("date", type=datetime.date.fromisoformat)
            if date is None:
                return common.error("Transaction date must not be empty")
            parent.date_ord = date.toordinal()
            parent.locked = "locked" in form

            payee = form.getlist("payee")
            description = form.getlist("description")
            category = form.getlist("category")
            tag = form.getlist("tag")
            amount = form.getlist("amount", utils.parse_real)

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
                    return common.error("Transaction split amount must not be empty")
                t_split.amount = a

            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.overlay_swap(event="update-transaction")


def split(uri: str) -> str:
    """GET, PUT & DELETE /h/transactions/<uri>/split.

    Args:
        uri: Transaction URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        categories = TransactionCategory.map_name(s)

    form = flask.request.form

    payee: list[str | None] = list(form.getlist("payee"))
    description: list[str | None] = list(form.getlist("description"))
    category: list[str] = form.getlist("category")
    tag: list[str | None] = list(form.getlist("tag"))
    amount: list[Decimal | None] = list(form.getlist("amount", utils.parse_real))

    if flask.request.method == "PUT":
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

        with p.get_session() as s:
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
            parent: Transaction = web_utils.find(s, Transaction, uri)  # type: ignore[attr-defined]
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
        with p.get_session() as s:
            parent: Transaction = web_utils.find(s, Transaction, uri)  # type: ignore[attr-defined]
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

    with p.get_session() as s:
        parent: Transaction = web_utils.find(s, Transaction, uri)  # type: ignore[attr-defined]
        form = flask.request.form

        amount = form.getlist("amount", utils.parse_real)
        current = sum(filter(None, amount))

        return flask.render_template(
            "transactions/edit-remaining.jinja",
            remaining=parent.amount - current,
        )


ROUTES: Routes = {
    "/transactions": (page_all, ["GET"]),
    "/h/transactions/table": (table, ["GET"]),
    "/h/transactions/options/<path:field>": (options, ["GET"]),
    "/h/transactions/t/<path:uri>/edit": (edit, ["GET", "POST"]),
    "/h/transactions/t/<path:uri>/split": (split, ["GET", "PUT", "DELETE"]),
    "/h/transactions/t/<path:uri>/remaining": (remaining, ["POST"]),
}
