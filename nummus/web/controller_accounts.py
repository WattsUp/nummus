"""Account API Controller
"""

import datetime

import flask

from nummus import portfolio
from nummus import custom_types as t
from nummus.models import (Account, AccountCategory, Transaction,
                           TransactionSplit)
from nummus.web import common, controller_transactions
from nummus.web.common import HTTPError


def create() -> flask.Response:
  """POST /api/accounts

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: t.JSONObj = flask.request.json
  name = req["name"]
  institution = req["institution"]
  category = common.parse_enum(req["category"], AccountCategory)

  with p.get_session() as s:
    acct = Account(name=name, institution=institution, category=category)
    s.add(acct)
    s.commit()
    return flask.jsonify(acct), 201, {"Location": f"/api/accounts/{acct.uuid}"}


def get(account_uuid: str) -> flask.Response:
  """GET /api/accounts/{account_uuid}

  Args:
    account_uuid: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    acct = common.find_account(s, account_uuid)
    return flask.jsonify(acct)


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
    acct = common.find_account(s, account_uuid)

    req: t.JSONObj = flask.request.json
    d: t.JSONObj = {}
    d["name"] = req["name"]
    d["institution"] = req["institution"]
    d["category"] = common.parse_enum(req["category"], AccountCategory)

    acct.update(d)
    s.commit()
    return flask.jsonify(acct)


def delete(account_uuid: str) -> flask.Response:
  """DELETE /api/accounts/{account_uuid}

  Args:
    account_uuid: UUID of Account to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    acct = common.find_account(s, account_uuid)

    # Delete the transactions as well
    query = s.query(TransactionSplit).where(
        TransactionSplit.account_id == acct.id)
    for v in query.all():
      s.delete(v)
    s.commit()
    query = s.query(Transaction).where(Transaction.account_id == acct.id)
    for v in query.all():
      s.delete(v)
    s.commit()
    s.delete(acct)
    s.commit()
    return None


def get_all() -> flask.Response:
  """GET /api/accounts

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: t.JSONObj = flask.request.args.to_dict()
  category = common.parse_enum(args.get("category"), AccountCategory)
  search = args.get("search")

  with p.get_session() as s:
    query = s.query(Account)
    if category is not None:
      query = query.where(Account.category == category)

    query = common.search(query, Account, search)
    accounts = query.all()
    response = {"accounts": accounts, "count": len(accounts)}
    return flask.jsonify(response)


def get_transactions(account_uuid: str) -> flask.Response:
  """GET /api/accounts/{account_uuid}/transactions

  Args:
    account_uuid: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  # Use controller_transactions' implementation
  args = flask.request.args.to_dict()
  args["account"] = account_uuid
  return controller_transactions.get_all(args)


def get_value(account_uuid: str) -> flask.Response:
  """GET /api/accounts/{account_uuid}/value

  Args:
    account_uuid: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.JSONObj = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    acct = common.find_account(s, account_uuid)

    dates, values, _ = acct.get_value(start, end)
    response = {"values": values, "dates": dates}
    return flask.jsonify(response)
