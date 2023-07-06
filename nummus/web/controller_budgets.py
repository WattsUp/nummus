"""Budget API Controller
"""

import typing as t

import datetime

import flask

from nummus import portfolio
from nummus.models import Budget
from nummus.web import common
from nummus.web.common import HTTPError


def create() -> flask.Response:
  """POST /api/budgets

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  req: t.Dict[str, object] = flask.request.json
  req_categories: t.Dict[str, float] = req["categories"]
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
    return flask.jsonify(b), 201, {"Location": f"/api/budgets/{b.uuid}"}


def get(budget_uuid: str) -> flask.Response:
  """GET /api/budgets/{budget_uuid}

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
  """PUT /api/budgets/{budget_uuid}

  Args:
    budget_uuid: UUID of Budget to update

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    b = common.find_budget(s, budget_uuid)

    req: t.Dict[str, object] = flask.request.json
    b.date = common.parse_date(req["date"])
    b.categories = req["categories"]

    s.commit()
    return flask.jsonify(b)


def delete(budget_uuid: str) -> flask.Response:
  """DELETE /api/budgets/{budget_uuid}

  Args:
    budget_uuid: UUID of Budget to delete

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  with p.get_session() as s:
    b = common.find_budget(s, budget_uuid)

    s.delete(b)
    s.commit()
    return None


def get_all() -> flask.Response:
  """GET /api/budgets

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start"))
  end = common.parse_date(args.get("end", today))
  sort = str(args.get("sort", "oldest"))
  limit = int(args.get("limit", 50))
  offset = int(args.get("offset", 0))

  with p.get_session() as s:
    query = s.query(Budget).where(Budget.date <= end)
    if start is not None:
      if end <= start:
        raise HTTPError(422, detail="End date must be after Start date")
      query = query.where(Budget.date >= start)

    # Apply ordering
    if sort == "oldest":
      query = query.order_by(Budget.date)
    else:
      query = query.order_by(Budget.date.desc())

    page, count, next_offset = common.paginate(query, limit, offset)
    response = {"budgets": page, "count": count, "next_offset": next_offset}
    return flask.jsonify(response)
