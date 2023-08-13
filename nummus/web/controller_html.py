"""Web controllers for HTML pages
"""

import datetime
from decimal import Decimal

import flask

from nummus import portfolio
from nummus import custom_types as t
from nummus.models import Account, AccountCategory


def get_home() -> str:
  """GET /

  Returns:
    string HTML page response
  """
  return flask.render_template("index.html")


def get_sidebar() -> str:
  """GET /sidebar

  Returns:
    string HTML page response
  """
  # Create sidebar context
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  assets = Decimal(0)
  liabilities = Decimal(0)

  categories_total: t.Dict[AccountCategory, t.Real] = {}
  categories: t.Dict[AccountCategory, t.List[t.DictAny]] = {}

  with p.get_session() as s:
    for acct in s.query(Account).all():
      acct: Account

      _, values, _ = acct.get_value(today, today)
      v = values[0]
      if v > 0:
        assets += v
      else:
        liabilities += v

      acct_dict: t.DictAny = {
          "name": acct.name,
          "institution": acct.institution,
          "value": v,
          "updated_days_ago": (today - acct.updated_on).days
      }

      if acct.category not in categories:
        categories_total[acct.category] = v
        categories[acct.category] = [acct_dict]
      else:
        categories_total[acct.category] += v
        categories[acct.category].append(acct_dict)

  asset_width = round(assets / (assets - liabilities) * 100, 2)
  context: t.DictStr = {
      "net-worth": assets + liabilities,
      "assets": assets,
      "liabilities": liabilities,
      "assets-w": asset_width,
      "liabilities-w": 100 - asset_width,
      "categories": {
          cat: (total, categories[cat])
          for cat, total in categories_total.items()
      },
  }
  return flask.render_template("sidebar.html", context=context)
