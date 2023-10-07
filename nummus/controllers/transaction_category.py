"""TransactionCategory controllers
"""

import flask
from werkzeug import exceptions

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.models import (TransactionCategory, TransactionCategoryGroup,
                           TransactionSplit)


def overlay() -> str:
  """GET /h/transaction_categories

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
          "locked": cat.locked
      }
      if cat.group == TransactionCategoryGroup.INCOME:
        income.append(cat_d)
      elif cat.group == TransactionCategoryGroup.EXPENSE:
        expense.append(cat_d)
      elif cat.group == TransactionCategoryGroup.OTHER:
        other.append(cat_d)
      else:
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
  """GET & POST /h/transaction_categories/new

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  name = None
  group = None

  error: str = None
  if flask.request.method == "POST":
    form = flask.request.form
    name = form["name"].strip()
    group = web_utils.parse_enum(form["group"], TransactionCategoryGroup)

    if name == "":
      error = "Category name must not be empty"
    else:
      with p.get_session() as s:
        query = s.query(TransactionCategory)
        query = query.where(TransactionCategory.name == name)
        if query.count() > 0:
          error = "Category names must be unique"
        else:
          cat = TransactionCategory(name=name, group=group, locked=False)
          s.add(cat)
          s.commit()
          return overlay()

  ctx: t.DictAny = {
      "uuid": None,
      "name": name,
      "group": group,
      "group_type": TransactionCategoryGroup,
      "locked": False,
  }

  return flask.render_template(
      "transaction_categories/edit.html",
      category=ctx,
      error=error,
  )


def edit(path_uuid: str) -> str:
  """GET & POST /h/transaction_categories/<category_uuid>/edit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    cat: TransactionCategory = web_utils.find(s, TransactionCategory, path_uuid)
    name = cat.name
    group = cat.group

    if cat.locked:
      raise exceptions.Forbidden(f"Locked category {cat.name} cannot be "
                                 "modified")

    error: str = None
    if flask.request.method == "POST":
      form = flask.request.form
      name = form["name"].strip()
      group = web_utils.parse_enum(form.get("group"), TransactionCategoryGroup)

      if name == "":
        error = "Category name must not be empty"
      else:
        query = s.query(TransactionCategory.id)
        query = query.where(TransactionCategory.name == name)
        query = query.where(TransactionCategory.id != cat.id)
        if query.count() > 0:
          error = "Category names must be unique"
        else:
          cat.name = name
          if group is not None:
            cat.group = group
          s.commit()
          return overlay()

    ctx: t.DictAny = {
        "uuid": cat.uuid,
        "name": name,
        "group": group,
        "group_type": TransactionCategoryGroup,
        "locked": cat.locked,
    }

  return flask.render_template(
      "transaction_categories/edit.html",
      category=ctx,
      error=error,
  )


def delete(path_uuid: str) -> str:
  """GET & POST /h/transaction_categories/<category_uuid>/delete

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    cat: TransactionCategory = web_utils.find(s, TransactionCategory, path_uuid)

    if cat.locked:
      raise exceptions.Forbidden(f"Locked category {cat.name} cannot be "
                                 "deleted")

    error: str = None
    if flask.request.method == "POST":
      # Move all transactions to Uncategorized
      query = s.query(TransactionCategory)
      query = query.where(TransactionCategory.name == "Uncategorized")
      uncategorized = query.first()
      if uncategorized is None:
        raise ValueError("Could not find Uncategorized id")

      query = s.query(TransactionSplit)
      query = query.where(TransactionSplit.category_id == cat.id)
      for t_split in query.all():
        t_split.category_id = uncategorized.id
      s.delete(cat)
      s.commit()
      return overlay()

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
      error=error,
  )


ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/h/txn-categories": (overlay, ["GET"]),
    "/h/txn-categories/new": (new, ["GET", "POST"]),
    "/h/txn-categories/<path:path_uuid>/edit": (edit, ["GET", "POST"]),
    "/h/txn-categories/<path:path_uuid>/delete": (delete, ["GET", "POST"])
}
