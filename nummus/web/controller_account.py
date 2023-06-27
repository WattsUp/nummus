"""Web controllers for HTML pages
"""

from typing import Dict

import uuid

import connexion
import flask

from nummus import portfolio
from nummus.models import Account, AccountCategory


def create() -> flask.Response:
  """POST /api/account

  Returns:
    JSON response, see api.yaml for details
  """
  req: Dict[str, object] = flask.request.json
  name = str(req["name"])
  institution = str(req["institution"])
  category = AccountCategory.parse(req["category"])

  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  a = Account(name=name, institution=institution, category=category)
  with p.get_session() as s:
    s.add(a)
    s.commit()
    return flask.jsonify(a)


def get(account_id: str) -> flask.Response:
  """GET /api/account/{account_id}

  Args:
    account_id: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  try:
    account_id = str(uuid.UUID(account_id))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {account_id}") from e
  with p.get_session() as s:
    account = s.query(Account).where(Account.uuid == account_id).first()
    if account is None:
      return connexion.problem(404, "Account not found",
                               f"{account_id} not found in Portfolio")
    return flask.jsonify(account)


def update(account_id: str) -> flask.Response:
  """PUT /api/account/{account_id}

  Args:
    account_id: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  try:
    account_id = str(uuid.UUID(account_id))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {account_id}") from e
  with p.get_session() as s:
    account = s.query(Account).where(Account.uuid == account_id).first()
    if account is None:
      return connexion.problem(404, "Account not found",
                               f"{account_id} not found in Portfolio")

    req: Dict[str, object] = flask.request.json
    account.update(req)
    return flask.jsonify(account)


def delete(account_id: str) -> flask.Response:
  """DELETE /api/account/{account_id}

  Args:
    account_id: UUID of Account to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  try:
    account_id = str(uuid.UUID(account_id))
  except ValueError as e:
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Badly formed UUID: {account_id}") from e
  with p.get_session() as s:
    account = s.query(Account).where(Account.uuid == account_id).first()
    if account is None:
      return connexion.problem(404, "Account not found",
                               f"{account_id} not found in Portfolio")
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
  args: Dict[str, object] = flask.request.args.to_dict()
  filter_category = AccountCategory.parse(args.get("category"))

  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  with p.get_session() as s:
    query = s.query(Account)
    if filter_category is not None:
      query = query.where(Account.category == filter_category)

    matches = query.all()
    return flask.jsonify(matches)
