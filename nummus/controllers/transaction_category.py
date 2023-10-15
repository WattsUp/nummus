"""TransactionCategory controllers
"""

import flask
import sqlalchemy.exc
from werkzeug import exceptions

from nummus import custom_types as t
from nummus import portfolio, web_utils
from nummus.controllers import common
from nummus.models import (
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)


def overlay() -> str:
    """GET /h/txn-categories

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio

    with p.get_session() as s:
        income: t.List[t.DictAny] = []
        expense: t.List[t.DictAny] = []
        other: t.List[t.DictAny] = []

        for cat in s.query(TransactionCategory).all():
            cat_d: t.DictAny = {
                "uuid": cat.uuid,
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
                raise ValueError(f"Unknown category type: {cat.group}")

        income = sorted(income, key=lambda cat: cat["name"])
        expense = sorted(expense, key=lambda cat: cat["name"])
        other = sorted(other, key=lambda cat: cat["name"])

        ctx: t.DictAny = {"income": income, "expense": expense, "other": other}

    return flask.render_template(
        "transaction_categories/table.html",
        categories=ctx,
    )


def new() -> str:
    """GET & POST /h/txn-categories/new

    Returns:
        string HTML response
    """
    if flask.request.method == "GET":
        ctx: t.DictAny = {
            "uuid": None,
            "name": None,
            "group": None,
            "group_type": TransactionCategoryGroup,
            "locked": False,
        }

        return flask.render_template("transaction_categories/edit.html", category=ctx)

    form = flask.request.form
    name = form["name"].strip()
    group = form.get("group", type=TransactionCategoryGroup.parse)

    try:
        with flask.current_app.app_context():
            p: portfolio.Portfolio = flask.current_app.portfolio
        with p.get_session() as s:
            cat = TransactionCategory(name=name, group=group, locked=False)
            s.add(cat)
            s.commit()
    except (sqlalchemy.exc.IntegrityError, ValueError) as e:
        return common.error(e)

    return common.overlay_swap(overlay())


def edit(path_uuid: str) -> str:
    """GET & POST /h/txn-categories/<category_uuid>/edit

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio

    with p.get_session() as s:
        cat: TransactionCategory = web_utils.find(s, TransactionCategory, path_uuid)

        if flask.request.method == "GET":
            ctx: t.DictAny = {
                "uuid": cat.uuid,
                "name": cat.name,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
            }

            return flask.render_template(
                "transaction_categories/edit.html",
                category=ctx,
            )

        if cat.locked:
            raise exceptions.Forbidden(f"Locked category {cat.name} cannot be modified")

        form = flask.request.form
        name = form["name"].strip()
        group = form.get("group", type=TransactionCategoryGroup.parse)

        try:
            cat.name = name
            cat.group = group
            s.commit()
        except (sqlalchemy.exc.IntegrityError, ValueError) as e:
            return common.error(e)

        return common.overlay_swap(overlay())


def delete(path_uuid: str) -> str:
    """GET & POST /h/txn-categories/<category_uuid>/delete

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio

    with p.get_session() as s:
        cat: TransactionCategory = web_utils.find(s, TransactionCategory, path_uuid)

        if flask.request.method == "GET":
            ctx: t.DictAny = {
                "uuid": cat.uuid,
                "name": cat.name,
                "group": cat.group,
                "group_type": TransactionCategoryGroup,
                "locked": cat.locked,
            }

            return flask.render_template(
                "transaction_categories/delete.html",
                category=ctx,
            )

        if cat.locked:
            raise exceptions.Forbidden(f"Locked category {cat.name} cannot be deleted")

        # Move all transactions to Uncategorized
        query = s.query(TransactionCategory)
        query = query.where(TransactionCategory.name == "Uncategorized")
        uncategorized = query.scalar()
        if uncategorized is None:  # pragma: no cover
            # Uncategorized is locked and cannot be deleted
            raise ValueError("Could not find Uncategorized id")

        query = s.query(TransactionSplit)
        query = query.where(TransactionSplit.category_id == cat.id)
        for t_split in query.all():
            t_split.category_id = uncategorized.id
        s.delete(cat)
        s.commit()

        return common.overlay_swap(overlay())


ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/h/txn-categories": (overlay, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/<path:path_uuid>/edit": (edit, ["GET", "POST"]),
    "/h/txn-categories/<path:path_uuid>/delete": (delete, ["GET", "POST"]),
}
