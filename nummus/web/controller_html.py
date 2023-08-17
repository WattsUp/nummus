"""Web controllers for HTML pages
"""

import datetime
from decimal import Decimal

import flask
import sqlalchemy

from nummus import portfolio
from nummus import custom_types as t
from nummus.models import Account, AccountCategory, Transaction


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
    # Get basic info
    accounts: t.Dict[str, t.DictAny] = {}
    query = s.query(Account)
    query = query.with_entities(Account.uuid, Account.name, Account.institution,
                                Account.category)
    for acct_uuid, name, institution, category in query.all():
      acct_uuid: str
      name: str
      institution: str
      category: AccountCategory
      accounts[acct_uuid] = {
          "name": name,
          "institution": institution,
          "category": category
      }

    # Get updated_on
    query = s.query(Transaction)
    query = query.with_entities(Transaction.account_uuid,
                                sqlalchemy.func.max(Transaction.date))  # pylint: disable=not-callable
    query = query.group_by(Transaction.account_id)
    for acct_uuid, updated_on in query.all():
      acct_uuid: str
      updated_on: datetime.date
      accounts[acct_uuid]["updated_days_ago"] = (today - updated_on).days

    # Get all Account values
    _, acct_values, _ = Account.all_get_value(s, today, today)
    for acct_uuid, values in acct_values.items():
      acct_dict = accounts[acct_uuid]
      v = values[0]
      if v > 0:
        assets += v
      else:
        liabilities += v
      acct_dict["value"] = v
      category = acct_dict["category"]

      if category not in categories:
        categories_total[category] = v
        categories[category] = [acct_dict]
      else:
        categories_total[category] += v
        categories[category].append(acct_dict)

  bar_total = assets - liabilities
  if bar_total == 0:
    asset_width = 0
    liabilities_width = 0
  else:
    asset_width = round(assets / (assets - liabilities) * 100, 2)
    liabilities_width = 100 - asset_width
  # TODO (WattsUp) Sort categories in preferred order
  # Then sort accounts in alphabetical order
  # Add account UUIDs for links
  context: t.DictStr = {
      "net-worth": assets + liabilities,
      "assets": assets,
      "liabilities": liabilities,
      "assets-w": asset_width,
      "liabilities-w": liabilities_width,
      "categories": {
          cat: (total, categories[cat])
          for cat, total in categories_total.items()
      },
  }
  return flask.render_template("sidebar.html", context=context)
