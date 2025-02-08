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
        "transaction_categories/index-content.jinja",
        "Transaction Categories",
        categories=ctx_categories(),
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
                or cat.name == "Uncategorized"
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
            "group_type": sorted(
                (
                    g
                    for g in TransactionCategoryGroup
                    if g != TransactionCategoryGroup.OTHER
                ),
                key=lambda g: g.name,
            ),
            "locked": False,
        }

        return flask.render_template("transaction_categories/edit.jinja", category=ctx)

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

    return common.dialog_swap()


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
                "group_type": sorted(
                    (
                        g
                        for g in TransactionCategoryGroup
                        if g != TransactionCategoryGroup.OTHER
                    ),
                    key=lambda g: g.name,
                ),
                "locked": cat.locked,
                "is_profit_loss": cat.is_profit_loss,
                "essential": cat.essential,
            }

            return flask.render_template(
                "transaction_categories/edit.jinja",
                category=ctx,
            )

        if flask.request.method == "DELETE":
            if cat.locked:
                msg = f"Locked category {cat.name} cannot be modified"
                raise exc.http.Forbidden(msg)
            # Move all transactions to Uncategorized
            query = s.query(TransactionCategory.id_).where(
                TransactionCategory.name == "Uncategorized",
            )
            try:
                uncategorized_id: int = query.one()[0]
            except exc.NoResultFound as e:  # pragma: no cover
                # Uncategorized is locked and cannot be deleted
                msg = "Could not find Uncategorized id"
                raise exc.ProtectedObjectNotFoundError(msg) from e

            s.query(TransactionSplit).where(
                TransactionSplit.category_id == cat.id_,
            ).update({"category_id": uncategorized_id})
            s.delete(cat)

            return common.dialog_swap(event="update-transaction")

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

        name_clean = utils.strip_emojis(name).strip()
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

        return common.dialog_swap(event="update-transaction")


ROUTES: Routes = {
    "/txn-categories": (page, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>": (category, ["GET", "PUT", "DELETE"]),
}
