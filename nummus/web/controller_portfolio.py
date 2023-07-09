"""Portfolio API Controller
"""

import typing as t

import datetime

import flask

from nummus import portfolio
from nummus.models import Account, AccountCategory
from nummus.web import common
from nummus.web.common import HTTPError


def get_value() -> flask.Response:
  """GET /api/portfolio/value

  Args:
    account_uuid: UUID of Account to find

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  category = common.parse_enum(args.get("account_category"), AccountCategory)
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    query = s.query(Account)
    if category is not None:
      query = query.where(Account.category == category)

    # Prepare dates
    dates: t.List[datetime.date] = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    total: t.List[float] = [0] * len(dates)
    assets: t.List[float] = [0] * len(dates)
    liabilities: t.List[float] = [0] * len(dates)

    for acct in query.all():
      _, a_values, _ = acct.get_value(start, end)
      for i, v in enumerate(a_values):
        total[i] += v
        if v >= 0:
          assets[i] += v
        else:
          liabilities[i] += v

    response = {
        "total": total,
        "assets": assets,
        "liabilities": liabilities,
        "dates": dates
    }
    return flask.jsonify(response)
