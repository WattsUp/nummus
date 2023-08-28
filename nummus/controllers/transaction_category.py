"""TransactionCategory controllers
"""

import flask
from werkzeug import exceptions

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.models import TransactionCategory, TransactionCategoryGroup


def overlay_categories() -> str:
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

  return flask.render_template("transaction_categories/table.html",
                               categories=ctx)


def new_category() -> str:
  """GET & POST /h/transaction_categories/new

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  error: str = None
  if flask.request.method == "POST":
    form = flask.request.form
    name = form["name"].strip()
    group = web_utils.parse_enum(form["group"], TransactionCategoryGroup)

    if name == "":
      error = "Category name must not be empty"
    else:
      with p.get_session() as s:
        cat = TransactionCategory(name=name, group=group, custom=True)
        s.add(cat)
        s.commit()
      return overlay_categories()

  ctx: t.DictAny = {
      "uuid": None,
      "name": None,
      "group": None,
      "group_type": TransactionCategoryGroup,
      "custom": None,
      "locked": cat.locked,
      "error": error
  }

  return flask.render_template("transaction_categories/edit.html", category=ctx)


def edit_category(path_uuid: str) -> str:
  """GET & POST /h/transaction_categories/<category_uuid>/edit

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    cat: TransactionCategory = web_utils.find(s, TransactionCategory, path_uuid)

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
      elif group is not None and not cat.custom:
        raise exceptions.Forbidden(f"Non-custom category {cat.name} cannot "
                                   "have group changed")
      else:
        cat.name = name
        if group is not None:
          cat.group = group
        s.commit()
        return overlay_categories()

    ctx: t.DictAny = {
        "uuid": cat.uuid,
        "name": cat.name,
        "group": cat.group,
        "group_type": TransactionCategoryGroup,
        "custom": cat.custom,
        "locked": cat.locked,
        "error": error
    }

  return flask.render_template("transaction_categories/edit.html", category=ctx)


def delete_category(path_uuid: str) -> str:
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
    if not cat.custom:
      raise exceptions.Forbidden(f"Non-custom category {cat.name} cannot be "
                                 "deleted")

    error: str = None
    if flask.request.method == "POST":
      print("TODO Deleting...")

    ctx: t.DictAny = {
        "uuid": cat.uuid,
        "name": cat.name,
        "group": cat.group,
        "group_type": TransactionCategoryGroup,
        "custom": cat.custom,
        "locked": cat.locked,
        "error": error
    }

  return flask.render_template("transaction_categories/delete.html",
                               category=ctx)
