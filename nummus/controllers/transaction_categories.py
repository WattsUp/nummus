"""TransactionCategory controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flask

from nummus import exceptions as exc
from nummus import utils, web
from nummus.controllers import base
from nummus.models import (
    query_count,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


def page() -> flask.Response:
    """GET /txn-categories.

    Returns:
        string HTML response

    """
    p = web.portfolio

    with p.begin_session() as s:
        return base.page(
            "transaction-categories/page.jinja",
            "Transaction categories",
            groups=ctx_categories(s),
        )


def new() -> str | flask.Response:
    """GET & POST /h/txn-categories/new.

    Returns:
        string HTML response

    """
    if flask.request.method == "GET":
        ctx: dict[str, object] = {
            "uri": None,
            "name": None,
            "emoji": None,
            "group": None,
            "group_type": TransactionCategoryGroup,
            "locked": False,
        }

        return flask.render_template("transaction-categories/edit.jinja", category=ctx)

    form = flask.request.form
    name = form["name"].strip()
    group = form.get("group", type=TransactionCategoryGroup)
    is_profit_loss = "is-pnl" in form
    essential_spending = "essential-spending" in form

    try:
        p = web.portfolio
        with p.begin_session() as s:
            cat = TransactionCategory(
                emoji_name=name,
                group=group,
                locked=False,
                is_profit_loss=is_profit_loss,
                asset_linked=False,
                essential_spending=essential_spending,
            )
            s.add(cat)
    except (exc.IntegrityError, exc.InvalidORMValueError) as e:
        return base.error(e)

    return base.dialog_swap(
        event="category",
        snackbar=f"Created category {name}",
    )


def category(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/txn-categories/c/<uri>.

    Args:
        uri: TransactionCategory URI

    Returns:
        string HTML response

    Raises:
        Forbidden: If locked category is edited

    """
    p = web.portfolio
    with p.begin_session() as s:
        cat = base.find(s, TransactionCategory, uri)

        if flask.request.method == "GET":
            ctx: dict[str, object] = {
                "uri": uri,
                "name": cat.emoji_name,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
                "is_profit_loss": cat.is_profit_loss,
                "essential_spending": cat.essential_spending,
            }

            return flask.render_template(
                "transaction-categories/edit.jinja",
                category=ctx,
            )

        if flask.request.method == "DELETE":
            if cat.locked:
                msg = f"Locked category {cat.name} cannot be modified"
                raise exc.http.Forbidden(msg)
            # Move all transactions to uncategorized
            uncategorized_id, _ = TransactionCategory.uncategorized(s)

            s.query(TransactionSplit).where(
                TransactionSplit.category_id == cat.id_,
            ).update({"category_id": uncategorized_id})
            s.delete(cat)

            return base.dialog_swap(
                event="category",
                snackbar=f"Deleted category {cat.emoji_name}",
            )

        form = flask.request.form
        name = form["name"]
        group = TransactionCategoryGroup(form["group"])
        is_profit_loss = "is-pnl" in form
        essential_spending = "essential-spending" in form

        name_clean = TransactionCategory.clean_emoji_name(name)
        if cat.locked and name_clean != cat.name:
            return base.error("May only add/remove emojis on locked category")

        try:
            with s.begin_nested():
                cat.emoji_name = name
                if not cat.locked:
                    cat.group = group
                    cat.is_profit_loss = is_profit_loss
                    cat.essential_spending = essential_spending
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return base.error(e)

        return base.dialog_swap(
            event="category",
            snackbar="All changes saved",
        )


def validation() -> str:
    """GET /h/txn-categories/validation.

    Returns:
        string HTML response

    """
    p = web.portfolio
    args = flask.request.args
    uri = args.get("uri")
    category_id = uri and TransactionCategory.uri_to_id(uri)
    if "name" in args:
        name = TransactionCategory.clean_emoji_name(args["name"])
        if not name:
            return "Required"
        if len(name) < utils.MIN_STR_LEN:
            return f"{utils.MIN_STR_LEN} characters required"
        with p.begin_session() as s:
            # Only get original name if locked
            locked_name = (
                s.query(TransactionCategory.name)
                .where(
                    TransactionCategory.id_ == category_id,
                    TransactionCategory.locked,
                )
                .scalar()
            )
            if locked_name and locked_name != name:
                return "May only add/remove emojis"
            n = query_count(
                s.query(TransactionCategory).where(
                    TransactionCategory.name == name,
                    TransactionCategory.id_ != category_id,
                ),
            )
            if n != 0:
                return "Must be unique"
        return ""

    raise NotImplementedError


def ctx_categories(
    s: orm.Session,
) -> dict[TransactionCategoryGroup, list[base.NamePair]]:
    """Get the context required to build the categories table.

    Args:
        s: SQL session to use

    Returns:
        List of HTML context

    """
    groups: dict[TransactionCategoryGroup, list[base.NamePair]] = {
        TransactionCategoryGroup.INCOME: [],
        TransactionCategoryGroup.EXPENSE: [],
        TransactionCategoryGroup.TRANSFER: [],
        TransactionCategoryGroup.OTHER: [],
    }
    query = s.query(TransactionCategory).order_by(TransactionCategory.name)
    for cat in query.yield_per(YIELD_PER):
        cat_d = base.NamePair(cat.uri, cat.emoji_name)
        if cat.group != TransactionCategoryGroup.OTHER or cat.name == "uncategorized":
            groups[cat.group].append(cat_d)

    return groups


ROUTES: base.Routes = {
    "/txn-categories": (page, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>": (category, ["GET", "PUT", "DELETE"]),
    "/h/txn-categories/validation": (validation, ["GET"]),
}
