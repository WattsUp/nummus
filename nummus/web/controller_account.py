"""Account API Controller
"""

from typing import Dict

import uuid

import connexion
from sqlalchemy import orm
import flask

from nummus import portfolio
from nummus.models import Account, AccountCategory


def find(s: orm.Session, query: str) -> Account:
  """Find the matching Account by UUID

  Args:
    s: SQL session to search
    query: Account UUID to find, will clean first
  
  Returns:
    Account

  Raises:
    BadRequestProblem if UUID is malformed
    ProblemException if Account is not found
  """
  try:
    account_uuid = str(uuid.UUID(query))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {query}") from e
  a = s.query(Account).where(Account.uuid == account_uuid).first()
  if a is None:
    raise connexion.exceptions.ProblemException(
        status=404, detail=f"{account_uuid} not found in Portfolio")
  return a


def create() -> flask.Response:
  """POST /api/account

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: Dict[str, object] = flask.request.json
  name = str(req["name"])
  institution = str(req["institution"])
  category = AccountCategory.parse(req["category"])

  a = Account(name=name, institution=institution, category=category)
  with p.get_session() as s:
    s.add(a)
    s.commit()
    return flask.jsonify(a)


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
    account = find(s, account_uuid)
    return flask.jsonify(account)


def update(account_uuid: str) -> flask.Response:
  """PUT /api/account/{account_uuid}

  Args:
    account_uuid: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    account = find(s, account_uuid)

    req: Dict[str, object] = flask.request.json
    account.update(req)
    return flask.jsonify(account)


def delete(account_uuid: str) -> flask.Response:
  """DELETE /api/account/{account_id}

  Args:
    account_id: UUID of Account to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    account = find(s, account_uuid)

    # Delete the transactions as well
    for t in account.transactions:
      for t_split in t.splits:
        s.delete(t_split)
      s.delete(t)
    s.delete(account)
    s.commit()
    return flask.jsonify(account)


def get_all() -> flask.Response:
  """Get all Accounts of Portfolio

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: Dict[str, object] = flask.request.args.to_dict()
  filter_category = AccountCategory.parse(args.get("category"))

  with p.get_session() as s:
    query = s.query(Account)
    if filter_category is not None:
      query = query.where(Account.category == filter_category)

    response = {"accounts": query.all()}
    return flask.jsonify(response)
