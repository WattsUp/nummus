"""TransactionCategory controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import emoji as emoji_mod
import flask

from nummus import exceptions as exc
from nummus import portfolio, web_utils
from nummus.controllers import common
from nummus.models import (
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from nummus.models.base import YIELD_PER

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


def _clean_emoji(text: str) -> tuple[str, str | None]:
    """Clean a string to a single emoji.

    Args:
        text: Text to Clean

    Returns:
        (ASCII text, First emoji or None)
    """
    # Grab only the first emoji
    tokens = list(emoji_mod.analyze(text, non_emoji=True))
    text_e = "".join(
        t.value.emoji for t in tokens if isinstance(t.value, emoji_mod.EmojiMatch)
    )
    text_t = "".join(t.value for t in tokens if isinstance(t.value, str)).strip()
    return text_t, text_e


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
        emoji: str | None
        locked: bool

    with p.get_session() as s:
        income: list[CategoryContext] = []
        expense: list[CategoryContext] = []
        other: list[CategoryContext] = []

        any_emojis = False
        query = s.query(TransactionCategory).where(
            TransactionCategory.name != "Securities Traded",
        )
        for cat in query.yield_per(YIELD_PER):
            cat_d: CategoryContext = {
                "uri": cat.uri,
                "name": cat.name,
                "emoji": cat.emoji,
                "locked": cat.locked,
            }
            any_emojis = any_emojis or cat.emoji
            if cat.group == TransactionCategoryGroup.INCOME:
                income.append(cat_d)
            elif cat.group == TransactionCategoryGroup.EXPENSE:
                expense.append(cat_d)
            elif cat.group == TransactionCategoryGroup.OTHER:
                other.append(cat_d)
            else:  # pragma: no cover
                msg = f"Unknown category type: {cat.group}"
                raise ValueError(msg)

        income = sorted(income, key=lambda cat: cat["name"])
        expense = sorted(expense, key=lambda cat: cat["name"])
        other = sorted(other, key=lambda cat: cat["name"])

        ctx = {"Income": income, "Expense": expense, "Other": other}

    return flask.render_template(
        "transaction_categories/table.jinja",
        any_emojis=any_emojis,
        categories=ctx,
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

        return flask.render_template("transaction_categories/edit.jinja", category=ctx)

    form = flask.request.form
    name = form["name"].strip()
    group = form.get("group", type=TransactionCategoryGroup)
    is_profit_loss = "is-pnl" in form

    name, emoji = _clean_emoji(name)

    try:
        with flask.current_app.app_context():
            p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
        with p.get_session() as s:
            cat = TransactionCategory(
                name=name,
                emoji=emoji,
                group=group,
                locked=False,
                is_profit_loss=is_profit_loss,
            )
            s.add(cat)
            s.commit()
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

    with p.get_session() as s:
        cat: TransactionCategory = web_utils.find(s, TransactionCategory, uri)  # type: ignore[attr-defined]

        if flask.request.method == "GET":
            ctx: dict[str, object] = {
                "uri": uri,
                "name": cat.name,
                "emoji": cat.emoji,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
                "is_profit_loss": cat.is_profit_loss,
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
            s.commit()

            return common.overlay_swap(overlay(), event="update-transaction")

        form = flask.request.form
        name = form["name"]
        group_s = form.get("group")
        group = TransactionCategoryGroup(group_s) if group_s else None
        is_profit_loss = "is-pnl" in form

        name, emoji = _clean_emoji(name)

        try:
            cat.emoji = emoji
            if not cat.locked:
                # Locked categorys can only change emoji
                cat.name = name
                if group is None:
                    return common.error("Transaction group must not be None")
                cat.group = group
                cat.is_profit_loss = is_profit_loss
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.overlay_swap(overlay(), event="update-transaction")


ROUTES: Routes = {
    "/h/txn-categories": (overlay, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>": (category, ["GET", "PUT", "DELETE"]),
}
