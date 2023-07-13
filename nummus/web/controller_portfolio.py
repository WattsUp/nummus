"""Portfolio API Controller
"""

import typing as t

import calendar
import datetime

import flask

from nummus import portfolio
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Budget, TransactionCategory)
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


def get_cash_flow(
    request_args: t.Dict[str, object] = None
) -> t.Union[flask.Response, t.Dict[str, object]]:
  """GET /api/portfolio/cash-flow

  Args:
    request_args: Override flask.request.args

  Returns:
    JSON response, see api.yaml for details
    If request_args is not None, the JSON response is returned before
    flask.jsonify is applied
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  if request_args is None:
    args = flask.request.args.to_dict()
  else:
    args = request_args

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

    categories: t.Dict[TransactionCategory, t.List[float]] = {
        cat: [0] * len(dates) for cat in TransactionCategory
    }
    categories["unknown-inflow"] = [0] * len(dates)  # Category is nullable
    categories["unknown-outflow"] = [0] * len(dates)  # Category is nullable

    for acct in query.all():
      acct: Account
      _, acct_categories = acct.get_cash_flow(start, end)
      for cat, values in acct_categories.items():
        values_sum = categories[cat]
        for i, v in enumerate(values):
          values_sum[i] += v

    if integrate:
      for cat, values in categories.items():
        integral = 0
        for i, v in enumerate(values):
          integral += v
          values[i] = integral

    total = [0] * len(dates)
    inflow = [0] * len(dates)
    outflow = [0] * len(dates)
    for cat, values in categories.items():
      for i, v in enumerate(values):
        total[i] += v
        if v > 0:
          inflow[i] += v
        else:
          outflow[i] += v

    # Convert to string
    def enum_to_str(e: TransactionCategory) -> str:
      if isinstance(e, str):
        return e
      return e.name.lower()

    response = {
        "total": total,
        "inflow": inflow,
        "outflow": outflow,
        "categories": {
            enum_to_str(cat): v for cat, v in categories.items()
        },
        "dates": dates
    }
    if request_args is not None:
      return response
    return flask.jsonify(response)


def get_budget() -> flask.Response:
  """GET /api/portfolio/budget

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio

  args: t.Dict[str, object] = flask.request.args.to_dict()
  integrate = bool(args.get("integrate", False))

  result = get_cash_flow(request_args=args)

  to_skip = ["income", "transfer", "instrument", "unknown-inflow"]

  outflow: t.List[float] = result["outflow"]
  outflow_categorized: t.Dict[str, t.List[float]] = {
      cat: v for cat, v in result["categories"].items() if cat not in to_skip
  }
  dates: t.List[datetime.date] = result["dates"]
  start = dates[0]
  end = dates[-1]

  target_categorized: t.Dict[str, t.List[float]] = {
      cat: [] for cat in outflow_categorized if cat != "unknown-outflow"
  }

  with p.get_session() as s:
    query = s.query(Budget).order_by(Budget.date)

    date = start

    current_categories = {cat: 0 for cat in target_categorized}
    for b in query.all():
      if b.date > end:
        continue
      while date < b.date:
        for k, v in current_categories.items():
          target_categorized[k].append(v)
        date += datetime.timedelta(days=1)

      for cat, v in b.categories.items():
        current_categories[cat] = v

    while date <= end:
      for k, v in current_categories.items():
        target_categorized[k].append(v)
      date += datetime.timedelta(days=1)

  # Adjust annual budget to daily amounts
  current_month = None
  daily_factor = 0
  factors = []
  for date in dates:
    if date.month != current_month:
      current_month = date.month
      month_len = calendar.monthrange(date.year, date.month)[1]
      # Daily budget = (annual budget) / (12 months) / (days in month)
      # So the sum(budget[any single month]) = annual / 12
      daily_factor = 1 / (12 * month_len)
    factors.append(daily_factor)

  for cat, values in target_categorized.items():
    target_categorized[cat] = [v * f for v, f in zip(values, factors)]

  if integrate:
    for cat, values in target_categorized.items():
      integral = 0
      for i, v in enumerate(values):
        integral += v
        values[i] = integral

  # Sum for total
  target = [0] * len(dates)
  for cat, values in target_categorized.items():
    for i, v in enumerate(values):
      target[i] += v

  response = {
      "outflow": outflow,
      "outflow_categorized": outflow_categorized,
      "target": target,
      "target_categorized": target_categorized,
      "dates": dates
  }

  return flask.jsonify(response)
