"""Web controllers for HTML pages
"""

from typing import Dict

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
  expected_keys = {"name", "institution", "category"}
  if expected_keys != req.keys():
    extra = list(req.keys() - expected_keys)
    raise connexion.exceptions.BadRequestProblem(
        detail=f"Extra Request Keys: {extra}")

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


def get_all() -> str:
  """Get all Accounts of Portfolio
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
