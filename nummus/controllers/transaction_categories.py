"""TransactionCategory controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import exceptions as exc
from nummus import portfolio, utils, web_utils
from nummus.controllers import common
from nummus.models import (
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


def page() -> flask.Response:
    """GET /txn-categories.

    Returns:
        string HTML response
    """
    return common.page(
        "transaction-categories/page.jinja",
        "Transaction Categories",
        ctx=ctx_categories(),
    )


def ctx_categories() -> dict[str, object]:
    """Get the context required to build the categories table.

    Returns:
        List of HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    class CategoryContext(TypedDict):
        """Type definition for category context."""

        uri: str | None
        name: str

    with p.begin_session() as s:
        groups: dict[TransactionCategoryGroup, list[CategoryContext]] = {
            TransactionCategoryGroup.INCOME: [],
            TransactionCategoryGroup.EXPENSE: [],
            TransactionCategoryGroup.TRANSFER: [],
            TransactionCategoryGroup.OTHER: [],
        }
        query = s.query(TransactionCategory).order_by(TransactionCategory.name)
        for cat in query.yield_per(YIELD_PER):
            cat_d: CategoryContext = {
                "uri": cat.uri,
                "name": cat.emoji_name,
            }
            if (
                cat.group != TransactionCategoryGroup.OTHER
                or cat.name == "uncategorized"
            ):
                groups[cat.group].append(cat_d)

    return {
        "groups": groups,
    }


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
    essential = "essential" in form

    try:
        with flask.current_app.app_context():
            p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
        with p.begin_session() as s:
            cat = TransactionCategory(
                emoji_name=name,
                group=group,
                locked=False,
                is_profit_loss=is_profit_loss,
                asset_linked=False,
                essential=essential,
            )
            s.add(cat)
    except (exc.IntegrityError, exc.InvalidORMValueError) as e:
        return common.error(e)

    return common.dialog_swap(event="update-category")


def category(uri: str) -> str | flask.Response:
    """GET, PUT, & DELETE /h/txn-categories/<uri>.

    Args:
        uri: TransactionCategory URI

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        cat = web_utils.find(s, TransactionCategory, uri)

        if flask.request.method == "GET":
            ctx: dict[str, object] = {
                "uri": uri,
                "name": cat.emoji_name,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
                "is_profit_loss": cat.is_profit_loss,
                "essential": cat.essential,
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
            query = s.query(TransactionCategory.id_).where(
                TransactionCategory.name == "uncategorized",
            )
            try:
                uncategorized_id: int = query.one()[0]
            except exc.NoResultFound as e:  # pragma: no cover
                # Uncategorized is locked and cannot be deleted
                msg = "Could not find uncategorized id"
                raise exc.ProtectedObjectNotFoundError(msg) from e

            s.query(TransactionSplit).where(
                TransactionSplit.category_id == cat.id_,
            ).update({"category_id": uncategorized_id})
            s.delete(cat)

            return common.dialog_swap(event="update-category")

        form = flask.request.form
        name = form["name"]
        group_s = form.get("group")
        group = (
            TransactionCategoryGroup(group_s)
            if group_s
            else TransactionCategoryGroup.TRANSFER
        )
        is_profit_loss = "is-pnl" in form
        essential = "essential" in form

        name_clean = TransactionCategory.clean_emoji_name(name)
        if cat.locked and name_clean != cat.name:
            return common.error("Can only add/remove emojis on locked category")

        try:
            with s.begin_nested():
                cat.emoji_name = name
                if not cat.locked:
                    cat.group = group
                    cat.is_profit_loss = is_profit_loss
                cat.essential = essential
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.dialog_swap(event="update-category")


def validation() -> str:
    """GET /h/txn-categories/validation.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    args = flask.request.args
    uri = args.get("uri")
    category_id = uri and TransactionCategory.uri_to_id(uri)
    if "name" in args:
        name = TransactionCategory.clean_emoji_name(args["name"])
        if name == "":
            return "Required"
        if len(name) < utils.MIN_STR_LEN:
            return f"At least {utils.MIN_STR_LEN} characters required"
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
            n = (
                s.query(TransactionCategory)
                .where(
                    TransactionCategory.name == name,
                    TransactionCategory.id_ != category_id,
                )
                .count()
            )
            if n != 0:
                return "Must be unique"
    else:
        raise NotImplementedError
    return ""


ROUTES: Routes = {
    "/txn-categories": (page, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>": (category, ["GET", "PUT", "DELETE"]),
    "/h/txn-categories/validation": (validation, ["GET"]),
}
