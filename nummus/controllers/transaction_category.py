"""TransactionCategory controllers
"""

import flask

from nummus import portfolio
from nummus import custom_types as t
from nummus.models import TransactionCategory, TransactionCategoryType


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
      cat_d: t.DictAny = {"uuid": cat.uuid, "name": cat.name}
      if cat.type_ == TransactionCategoryType.INCOME:
        income.append(cat_d)
      elif cat.type_ == TransactionCategoryType.EXPENSE:
        expense.append(cat_d)
      elif cat.type_ == TransactionCategoryType.OTHER:
        other.append(cat_d)
      else:
        raise ValueError(f"Unknown category type: {cat.type_}")

    ctx: t.DictAny = {"income": income, "expense": expense, "other": other}

  return flask.render_template("transaction_categories/table.html",
                               categories=ctx)
