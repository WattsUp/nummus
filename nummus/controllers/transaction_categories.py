"""TransactionCategory controllers."""

from __future__ import annotations

import flask

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import portfolio, web_utils
from nummus.controllers import common
from nummus.models import (
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    YIELD_PER,
)


def overlay() -> str:
    """GET /h/txn-categories.

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.get_session() as s:
        income: list[t.DictAny] = []
        expense: list[t.DictAny] = []
        other: list[t.DictAny] = []

        for cat in s.query(TransactionCategory).all():
            cat_d: t.DictAny = {
                "uri": cat.uri,
                "name": cat.name,
                "locked": cat.locked,
            }
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

        ctx: t.DictAny = {"Income": income, "Expense": expense, "Other": other}

    return flask.render_template(
        "transaction_categories/table.jinja",
        categories=ctx,
    )


def new() -> str | flask.Response:
    """GET & POST /h/txn-categories/new.

    Returns:
        string HTML response
    """
    if flask.request.method == "GET":
        ctx: t.DictAny = {
            "uri": None,
            "name": None,
            "group": None,
            "group_type": TransactionCategoryGroup,
            "locked": False,
        }

        return flask.render_template("transaction_categories/edit.jinja", category=ctx)

    form = flask.request.form
    name = form["name"].strip()
    group = form.get("group", type=TransactionCategoryGroup)

    try:
        with flask.current_app.app_context():
            p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
        with p.get_session() as s:
            cat = TransactionCategory(name=name, group=group, locked=False)
            s.add(cat)
            s.commit()
    except (exc.IntegrityError, exc.InvalidORMValueError) as e:
        return common.error(e)

    return common.overlay_swap(overlay())


def edit(uri: str) -> str | flask.Response:
    """GET & POST /h/txn-categories/<uri>/edit.

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
            ctx: t.DictAny = {
                "uri": uri,
                "name": cat.name,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
            }

            return flask.render_template(
                "transaction_categories/edit.jinja",
                category=ctx,
            )

        if cat.locked:
            msg = f"Locked category {cat.name} cannot be modified"
            raise exc.http.Forbidden(msg)

        form = flask.request.form
        name = form["name"].strip()
        group = form.get("group", type=TransactionCategoryGroup)

        if group is None:
            return common.error("Transaction group must not be None")

        try:
            cat.name = name
            cat.group = group
            s.commit()
        except (exc.IntegrityError, exc.InvalidORMValueError) as e:
            return common.error(e)

        return common.overlay_swap(overlay(), event="update-transaction")


def delete(uri: str) -> str | flask.Response:
    """GET & POST /h/txn-categories/<uri>/delete.

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
            ctx: t.DictAny = {
                "uri": uri,
                "name": cat.name,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
            }

            return flask.render_template(
                "transaction_categories/delete.jinja",
                category=ctx,
            )

        if cat.locked:
            msg = f"Locked category {cat.name} cannot be deleted"
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

        query = s.query(TransactionSplit).where(TransactionSplit.category_id == cat.id_)
        for t_split in query.yield_per(YIELD_PER):
            t_split.category_id = uncategorized_id
        s.delete(cat)
        s.commit()

        return common.overlay_swap(overlay(), event="update-transaction")


ROUTES: t.Routes = {
    "/h/txn-categories": (overlay, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>/edit": (edit, ["GET", "POST"]),
    "/h/txn-categories/c/<path:uri>/delete": (delete, ["GET", "POST"]),
}
