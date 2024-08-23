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
    Asset,
    paginate,
    search,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


class _OptionContex(TypedDict):
    """Type definition for option context."""

    name: str
    name_clean: str
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
        endpoint="transactions.table",
        endpoint_new="transactions.new",
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
        endpoint="transactions.table",
        endpoint_new="transactions.new",
    )
    response = flask.make_response(html)
    args = dict(flask.request.args.lists())
    response.headers["HX-Push-Url"] = flask.url_for(
        "transactions.page_all",
        _anchor=None,
        _method=None,
        _scheme=None,
        _external=False,
        **args,
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

    with p.get_session() as s:
        args = flask.request.args

        id_mapping = None
        if field == "account":
            id_mapping = Account.map_name(s)
        elif field == "category":
            id_mapping = TransactionCategory.map_name(s)
        elif field not in {"payee", "tag"}:
            msg = f"Unexpected txns options: {field}"
            raise exc.http.BadRequest(msg)

        query, _, _, _ = table_unfiltered_query(s)

        search_str = args.get(f"search-{field}")

        return flask.render_template(
            "transactions/table-options.jinja",
            options=ctx_options(query, field, id_mapping, search_str=search_str),
            name=field,
            search_str=search_str,
            endpoint="transactions.table",
            endpoint_new="transactions.new",
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
        "asset": TransactionSplit.asset_id,
    }
    for (id_,) in query.with_entities(entities[field]).distinct():
        if id_ is None:
            continue
        name = id_mapping[id_] if id_mapping else id_
        name_clean = web_utils.strip_emojis(name).lower()
        item: _OptionContex = {
            "name": name,
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
    default_period: str = "this-month",
    *,
    no_other_group: bool = False,
    asset_transactions: bool = False,
) -> tuple[orm.Query, str, datetime.date | None, datetime.date]:
    """Create transactions table query without any column filters.

    Args:
        s: SQL session to use
        acct: Account to get transactions for, None will use filter queries
        default_period: Default period to use if no period given
        no_other_group: True to exclude transactions in the OTHER group
        asset_transactions: True will only get transactions with assets,
            False will only get transactions without assets

    Returns:
        (SQL query, period string, start date or None, end date)
    """
    args = flask.request.args

    period = args.get("period", default_period)
    start, end = web_utils.parse_period(
        period,
        args.get("start", type=datetime.date.fromisoformat),
        args.get("end", type=datetime.date.fromisoformat),
    )
    if start is None and acct is not None:
        opened_on_ord = acct.opened_on_ord
        start = (
            end if opened_on_ord is None else datetime.date.fromordinal(opened_on_ord)
        )
    end_ord = end.toordinal()

    transaction_ids = None
    if no_other_group:
        query = (
            s.query(TransactionCategory)
            .with_entities(TransactionCategory.id_)
            .where(
                TransactionCategory.group != TransactionCategoryGroup.OTHER,
            )
        )
        transaction_ids = {row[0] for row in query.all()}
    securities_traded_id = (
        s.query(TransactionCategory.id_)
        .where(TransactionCategory.name == "Securities Traded")
        .one()[0]
    )

    query = (
        s.query(TransactionSplit)
        .where(
            (
                TransactionSplit.category_id == securities_traded_id
                if asset_transactions
                else TransactionSplit.category_id != securities_traded_id
            ),
            TransactionSplit.date_ord <= end_ord,
        )
        .order_by(TransactionSplit.date_ord)
    )
    if start is not None:
        start_ord = start.toordinal()
        query = query.where(TransactionSplit.date_ord >= start_ord)
    if acct is not None:
        query = query.where(TransactionSplit.account_id == acct.id_)
    if transaction_ids is not None:
        query = query.where(TransactionSplit.category_id.in_(transaction_ids))

    return query, period, start, end


def ctx_table(
    acct: Account | None = None,
    default_period: str = "this-month",
    *,
    no_other_group: bool = False,
    asset_transactions: bool = False,
) -> tuple[dict[str, object], str]:
    """Get the context to build the transaction table.

    Args:
        acct: Account to get transactions for, None will use filter queries
        default_period: Default period to use if no period given
        no_other_group: True to exclude transactions in the OTHER group
        asset_transactions: True will only get transactions with assets,
            False will only get transactions without assets

    Returns:
        Dictionary HTML context, title of page
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        args = flask.request.args
        search_str = args.get("search", "").strip()
        locked = args.get("locked", type=utils.parse_bool)
        linked = args.get("linked", type=utils.parse_bool)
        page_len = 25
        offset = int(args.get("offset", 0))
        page_total = Decimal(0)

        accounts = Account.map_name(s)
        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.name,
                TransactionCategory.emoji,
            )
            .order_by(TransactionCategory.name)
        )
        if not asset_transactions:
            query = query.where(TransactionCategory.name != "Securities Traded")
        categories: dict[int, str] = {
            t_cat_id: (f"{emoji} {name}" if emoji else name)
            for t_cat_id, name, emoji in query.yield_per(YIELD_PER)
        }
        assets = Asset.map_name(s)

        query, period, start, end = table_unfiltered_query(
            s,
            acct,
            default_period,
            no_other_group=no_other_group,
            asset_transactions=asset_transactions,
        )

        # Get options with these filters
        options_account = ctx_options(query, "account", accounts)
        options_payee = ctx_options(query, "payee")
        options_category = ctx_options(query, "category", categories)
        options_tag = ctx_options(query, "tag")
        options_asset = ctx_options(query, "asset", assets)

        def merge(options: list[_OptionContex], selected: list[str]) -> list[str]:
            options_flat = [option["name"] for option in options]
            return [item for item in selected if item in options_flat]

        selected_accounts = merge(options_account, args.getlist("account"))
        selected_payees = merge(options_payee, args.getlist("payee"))
        selected_categories = merge(options_category, args.getlist("category"))
        selected_tags = merge(options_tag, args.getlist("tag"))
        selected_assets = merge(options_asset, args.getlist("asset"))

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

        if len(selected_assets) != 0:
            ids = [
                asset_id for asset_id, name in assets.items() if name in selected_assets
            ]
            query = query.where(TransactionSplit.asset_id.in_(ids))

        if locked is not None:
            query = query.where(TransactionSplit.locked == locked)
        if linked is not None:
            query = query.where(TransactionSplit.linked == linked)

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
            t_split_ctx = ctx_split(t_split, accounts, categories, assets)
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
        if linked is not None:
            filters.append("Linked" if linked else "Unlinked")
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
            "linked": linked,
            "options-account": options_account,
            "options-payee": options_payee,
            "options-category": options_category,
            "options-tag": options_tag,
            "options-asset": options_asset,
            "any-filters-account": len(selected_accounts) > 0,
            "any-filters-payee": len(selected_payees) > 0,
            "any-filters-category": len(selected_categories) > 0,
            "any-filters-tag": len(selected_tags) > 0,
            "any-filters-asset": len(selected_assets) > 0,
        }, title


def ctx_split(
    t_split: TransactionSplit,
    accounts: dict[int, str],
    categories: dict[int, str],
    assets: dict[int, str],
) -> dict[str, object]:
    """Get the context to build the transaction edit dialog.

    Args:
        t_split: TransactionSplit to build context for
        accounts: Dict {id: account name}
        categories: Dict {id: category name}
        assets: Dict {id: asset name}

    Returns:
        Dictionary HTML context
    """
    qty = t_split.asset_quantity or 0
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
        "linked": t_split.linked,
        "asset_name": assets[t_split.asset_id] if t_split.asset_id else None,
        "asset_price": abs(t_split.amount / qty) if qty else None,
        "asset_quantity": qty,
    }


def new(acct_uri: str | None = None) -> str | flask.Response:
    """GET & POST /h/transactions/new.

    Args:
        acct_uri: Account uri to make transaction for, None for blank

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        accounts = Account.map_name(s)
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
        date = form.get("date", type=datetime.date.fromisoformat)
        if date is None:
            return common.error("Transaction date must not be empty")
        amount = form.get("amount", type=utils.parse_real)
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
            txn = Transaction(
                account_id=accounts_rev[account],
                date_ord=date.toordinal(),
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
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        uri = txn.uri

        edit_overlay = transaction(uri, force_get=True)
        if not isinstance(edit_overlay, str):  # pragma: no cover
            msg = "Edit overlay did not return a string"
            raise TypeError(msg)
        # Adding transactions update account cause the balance changes
        return common.overlay_swap(edit_overlay, event="update-account")


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

    with p.get_session() as s:
        try:
            parent: Transaction = web_utils.find(s, Transaction, uri)  # type: ignore[attr-defined]
        except exc.http.BadRequest:
            child: TransactionSplit = web_utils.find(s, TransactionSplit, uri)  # type: ignore[attr-defined]
            parent = child.parent
        categories = TransactionCategory.map_name(s)
        query = (
            s.query(TransactionCategory)
            .with_entities(
                TransactionCategory.id_,
                TransactionCategory.name,
                TransactionCategory.emoji,
            )
            .where(TransactionCategory.name != "Securities Traded")
            .order_by(TransactionCategory.name)
        )
        categories: dict[int, str] = {
            t_cat_id: (f"{emoji} {name}" if emoji else name)
            for t_cat_id, name, emoji in query.yield_per(YIELD_PER)
        }
        assets = Asset.map_name(s)

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

            ctx_splits: list[dict[str, object]] = [
                ctx_split(t_split, accounts, categories, assets) for t_split in splits
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
        if flask.request.method == "DELETE":
            if parent.linked:
                return common.error("Cannot delete linked transaction")
            s.query(TransactionSplit).where(
                TransactionSplit.parent_id == parent.id_,
            ).delete()
            s.delete(parent)
            s.commit()
            # Adding transactions update account cause the balance changes
            return common.overlay_swap(event="update-account")

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
    """GET, POST & DELETE /h/transactions/<uri>/split.

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
    "/h/transactions/new": (new, ["GET", "POST"]),
    "/h/transactions/options/<path:field>": (table_options, ["GET"]),
    "/h/transactions/t/<path:uri>/split": (split, ["GET", "POST", "DELETE"]),
    "/h/transactions/t/<path:uri>/remaining": (remaining, ["POST"]),
    "/h/transactions/t/<path:uri>": (transaction, ["GET", "PUT", "DELETE"]),
}
