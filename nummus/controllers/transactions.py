"""Transaction controllers
"""

import flask

from nummus import portfolio, web_utils
from nummus import custom_types as t
from nummus.controllers import common
from nummus.models import Transaction


def page_all() -> str:
  """GET /transactions

  Returns:
    string HTML response
  """
  return flask.render_template("transactions.html", sidebar=common.sidebar())


def page_one(path_uuid: str) -> str:
  """GET /transactions/<transaction_uuid>

  Returns:
    string HTML response
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    txn: Transaction = web_utils.find(s, Transaction, path_uuid)
    data: t.DictAny = {
        "account": txn.account.name,
        "statement": txn.statement,
        "date": txn.date,
        "locked": txn.locked
    }
  return flask.render_template("transaction.html",
                               sidebar=common.sidebar(),
                               transaction=data)
