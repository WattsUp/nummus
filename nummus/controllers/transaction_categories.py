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


def overlay() -> str:
    """GET /h/txn-categories.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    class CategoryContext(TypedDict):
        """Type definition for category context."""

        uri: str | None
        name: str
        emoji_name: str | None
        locked: bool

    with p.begin_session() as s:
        income: list[CategoryContext] = []
        expense: list[CategoryContext] = []
        transfer: list[CategoryContext] = []

        query = s.query(TransactionCategory).where(
            TransactionCategory.group != TransactionCategoryGroup.OTHER,
        )
        for cat in query.yield_per(YIELD_PER):
            cat_d: CategoryContext = {
                "uri": cat.uri,
                "name": cat.name,
                "emoji_name": cat.emoji_name,
                "locked": cat.locked,
            }
            if cat.group == TransactionCategoryGroup.INCOME:
                income.append(cat_d)
            elif cat.group == TransactionCategoryGroup.EXPENSE:
                expense.append(cat_d)
            elif cat.group == TransactionCategoryGroup.TRANSFER:
                transfer.append(cat_d)
            else:  # pragma: no cover
                msg = f"Unknown category type: {cat.group}"
                raise ValueError(msg)

        income = sorted(income, key=lambda cat: cat["name"])
        expense = sorted(expense, key=lambda cat: cat["name"])
        transfer = sorted(transfer, key=lambda cat: cat["name"])

        ctx = {"Income": income, "Expense": expense, "Transfer": transfer}

        query = s.query(TransactionCategory.id_).where(
            TransactionCategory.name == "Uncategorized",
        )
        try:
            uncategorized_id: int = query.one()[0]
        except exc.NoResultFound as e:  # pragma: no cover
            # Uncategorized is locked and cannot be deleted
            msg = "Could not find Uncategorized id"
            raise exc.ProtectedObjectNotFoundError(msg) from e
        uncategorized_uri = TransactionCategory.id_to_uri(uncategorized_id)

    return flask.render_template(
        "transaction_categories/table.jinja",
        categories=ctx,
        uncategorized=uncategorized_uri,
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

    return common.overlay_swap(overlay())


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

            return common.overlay_swap(overlay(), event="update-transaction")

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

        return common.overlay_swap(overlay(), event="update-transaction")


ROUTES: Routes = {
    "/h/txn-categories": (overlay, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>": (category, ["GET", "PUT", "DELETE"]),
}
