"""Budget API Controller
"""

from typing import Dict

import datetime

import flask

from nummus import portfolio
from nummus.models import Budget
from nummus.web import common


def create() -> flask.Response:
  """POST /api/budget

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: Dict[str, object] = flask.request.json
  req_categories: Dict[str, float] = req["categories"]
  date = common.parse_date(req["date"])
  home = req_categories["home"]
  food = req_categories["food"]
  shopping = req_categories["shopping"]
  hobbies = req_categories["hobbies"]
  services = req_categories["services"]
  travel = req_categories["travel"]

  b = Budget(date=date,
             home=home,
             food=food,
             shopping=shopping,
             hobbies=hobbies,
             services=services,
             travel=travel)
  with p.get_session() as s:
    s.add(b)
    s.commit()
    return flask.jsonify(b)


def get(budget_uuid: str) -> flask.Response:
  """GET /api/budget/{budget_uuid}

  Args:
    budget_uuid: UUID of Budget to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    b = common.find_budget(s, budget_uuid)
    return flask.jsonify(b)


def update(budget_uuid: str) -> flask.Response:
  """PUT /api/budget/{budget_uuid}

  Args:
    budget_uuid: UUID of Budget to update

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    b = common.find_budget(s, budget_uuid)

    req: Dict[str, object] = flask.request.json
    b.date = common.parse_date(req["date"])
    b.categories = req["categories"]

    s.commit()
    return flask.jsonify(b)


def delete(budget_uuid: str) -> flask.Response:
  """DELETE /api/budget/{budget_uuid}

  Args:
    budget_uuid: UUID of Budget to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    b = common.find_budget(s, budget_uuid)

    response = flask.jsonify(b)

    s.delete(b)
    s.commit()
    return response


def get_all() -> flask.Response:
  """GET /api/budgets

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start"))
  end = common.parse_date(args.get("end", today))
  limit = int(args.get("limit", 50))
  offset = int(args.get("offset", 0))
  sort = str(args.get("sort", "oldest"))
  next_offset: int = None

  with p.get_session() as s:
    query = s.query(Budget).where(Budget.date <= end)
    if start is not None:
      query = query.where(Budget.date >= start)

    # Get total number from filters
    # TODO (WattsUp) replace if counting is too slow
    # https://datawookie.dev/blog/2021/01/sqlalchemy-efficient-counting/
    count = query.count()

    # Apply ordering
    if sort == "oldest":
      query = query.order_by(Budget.date)
    else:
      query = query.order_by(Budget.date.desc())

    page, count, next_offset = common.paginate(query, limit, offset)
    response = {"budgets": page, "count": count, "next_offset": next_offset}
    return flask.jsonify(response)
