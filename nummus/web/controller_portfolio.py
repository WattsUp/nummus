"""Portfolio API Controller
"""

import typing as t

import datetime

import flask

from nummus import portfolio
from nummus.models import Account, AccountCategory, Asset, AssetCategory
from nummus.web import common
from nummus.web.common import HTTPError


def get_value() -> flask.Response:
  """GET /api/portfolio/value

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  category = common.parse_enum(args.get("category"), AccountCategory)
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
      acct: Account
      _, acct_values, _ = acct.get_value(start, end)
      for i, v in enumerate(acct_values):
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


def get_value_by_account() -> flask.Response:
  """GET /api/portfolio/value-by-account

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  category = common.parse_enum(args.get("category"), AccountCategory)
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
    accounts: t.Dict[str, t.List[float]] = {}

    for acct in query.all():
      acct: Account
      _, acct_values, _ = acct.get_value(start, end)
      for i, v in enumerate(acct_values):
        total[i] += v
      accounts[acct.uuid] = acct_values

    response = {"total": total, "accounts": accounts, "dates": dates}
    return flask.jsonify(response)


def get_value_by_category() -> flask.Response:
  """GET /api/portfolio/value-by-category

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    query = s.query(Account)

    # Prepare dates
    dates: t.List[datetime.date] = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    total: t.List[float] = [0] * len(dates)
    categories: t.Dict[str, t.List[float]] = {
        k.name.lower(): [0] * len(dates) for k in AccountCategory
    }

    for acct in query.all():
      acct: Account
      _, acct_values, _ = acct.get_value(start, end)
      cat_values = categories[acct.category.name.lower()]
      for i, v in enumerate(acct_values):
        total[i] += v
        cat_values[i] += v

    response = {"total": total, "categories": categories, "dates": dates}
    return flask.jsonify(response)


def get_value_by_asset() -> flask.Response:
  """GET /api/portfolio/value-by-asset

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  category = common.parse_enum(args.get("category"), AssetCategory)
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    q_accts = s.query(Account)

    q_assets = s.query(Asset.uuid)
    if category is not None:
      q_assets = q_assets.where(Asset.category == category)
    allowed_assets: t.List[str] = [uuid for uuid, in q_assets.all()]

    # Prepare dates
    dates: t.List[datetime.date] = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    assets: t.Dict[str, t.List[float]] = {}

    for acct in q_accts.all():
      acct: Account
      _, _, acct_assets = acct.get_value(start, end)
      for a, a_values in acct_assets.items():
        if a not in allowed_assets:
          continue
        if a not in assets:
          assets[a] = a_values
        else:
          # Add on to existing
          a_values_sum = assets[a]
          for i, v in enumerate(a_values):
            a_values_sum[i] += v

    response = {"assets": assets, "dates": dates}
    return flask.jsonify(response)


def get_cash_flow() -> flask.Response:
  """GET /api/portfolio/cash-flow

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.Dict[str, object] = flask.request.args.to_dict()
  start = common.parse_date(args.get("start", today))
  end = common.parse_date(args.get("end", today))
  category = common.parse_enum(args.get("category"), AccountCategory)
  integrate = bool(args.get("integrate", False))
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

    inflow: t.List[float] = [0] * len(dates)
    outflow: t.List[float] = [0] * len(dates)

    for acct in query.all():
      acct: Account
      _, acct_in, acct_out = acct.get_cash_flow(start, end)
      for i, v in enumerate(acct_in):
        inflow[i] += v
      for i, v in enumerate(acct_out):
        outflow[i] += v

    if integrate:
      integral = 0
      for i, v in enumerate(inflow):
        integral += v
        inflow[i] = integral
      integral = 0
      for i, v in enumerate(outflow):
        integral += v
        outflow[i] = integral

    total = [sum(x) for x in zip(inflow, outflow)]

    response = {
        "total": total,
        "inflow": inflow,
        "outflow": outflow,
        "dates": dates
    }
    return flask.jsonify(response)
