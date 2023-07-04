"""Account API Controller
"""

from typing import Dict

import flask

from nummus import portfolio
from nummus.models import Account, AccountCategory
from nummus.web import common


def create() -> flask.Response:
  """POST /api/account

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: Dict[str, object] = flask.request.json
  name = req["name"]
  institution = req["institution"]
  category = common.parse_enum(req["category"], AccountCategory)

  a = Account(name=name, institution=institution, category=category)
  with p.get_session() as s:
    s.add(a)
    s.commit()
    return flask.jsonify(a), 201, {"Location": f"/api/account/{a.uuid}"}


def get(account_uuid: str) -> flask.Response:
  """GET /api/account/{account_uuid}

  Args:
    account_uuid: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_account(s, account_uuid)
    return flask.jsonify(a)


def update(account_uuid: str) -> flask.Response:
  """PUT /api/account/{account_uuid}

  Args:
    account_uuid: UUID of Account to update

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_account(s, account_uuid)

    req: Dict[str, object] = flask.request.json
    d: Dict[str, object] = {}
    d["name"] = req["name"]
    d["institution"] = req["institution"]
    d["category"] = common.parse_enum(req["category"], AccountCategory)

    a.update(d)
    s.commit()
    return flask.jsonify(a)


def delete(account_uuid: str) -> flask.Response:
  """DELETE /api/account/{account_uuid}

  Args:
    account_uuid: UUID of Account to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    a = common.find_account(s, account_uuid)

    # Delete the transactions as well
    for t in a.transactions:
      for t_split in t.splits:
        s.delete(t_split)
      s.delete(t)
    s.delete(a)
    s.commit()
    return None


def get_all() -> flask.Response:
  """GET /api/accounts

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: Dict[str, object] = flask.request.args.to_dict()
  category = common.parse_enum(args.get("category"), AccountCategory)
  search = args.get("search")

  with p.get_session() as s:
    query = s.query(Account)
    if category is not None:
      query = query.where(Account.category == category)

    query = common.search(s, query, Account, search)
    accounts = query.all()
    response = {"accounts": accounts, "count": len(accounts)}
    return flask.jsonify(response)
