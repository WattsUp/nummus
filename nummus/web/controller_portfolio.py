"""Portfolio API Controller
"""

import calendar
import datetime
from decimal import Decimal

import flask

from nummus import common, portfolio
from nummus import custom_types as t
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Budget, TransactionCategory)
from nummus.web import common as web_common
from nummus.web.common import HTTPError

# TODO (WattsUp) If other features use this data, move to Portfolio
# Aka no import controller_*


def get_value() -> flask.Response:
  """GET /api/portfolio/value

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.JSONObj = flask.request.args.to_dict()
  start = web_common.parse_date(args.get("start", today))
  end = web_common.parse_date(args.get("end", today))
  category = web_common.parse_enum(args.get("category"), AccountCategory)
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    query = s.query(Account)
    if category is not None:
      query = query.where(Account.category == category)

    # Prepare dates
    dates: t.Dates = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    total: t.Reals = [Decimal(0)] * len(dates)
    assets: t.Reals = [Decimal(0)] * len(dates)
    liabilities: t.Reals = [Decimal(0)] * len(dates)

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

  args: t.JSONObj = flask.request.args.to_dict()
  start = web_common.parse_date(args.get("start", today))
  end = web_common.parse_date(args.get("end", today))
  category = web_common.parse_enum(args.get("category"), AccountCategory)
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    query = s.query(Account)
    if category is not None:
      query = query.where(Account.category == category)

    # Prepare dates
    dates: t.Dates = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    total: t.Reals = [Decimal(0)] * len(dates)
    accounts: t.DictReals = {}

    for acct in query.all():
      acct: Account
      _, acct_values, _ = acct.get_value(start, end)
      for i, v in enumerate(acct_values):
        total[i] += v
      accounts[acct.uuid] = acct_values

    response = {"total": total, "accounts": accounts, "dates": dates}
    return flask.jsonify(response)


def get_value_by_category(request_args: t.JSONObj = None) -> flask.Response:
  """GET /api/portfolio/value-by-category

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

  start = web_common.parse_date(args.get("start", today))
  end = web_common.parse_date(args.get("end", today))
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    query = s.query(Account)

    # Prepare dates
    dates: t.Dates = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    total: t.Reals = [Decimal(0)] * len(dates)
    categories: t.DictReals = {
        k.name.lower(): [Decimal(0)] * len(dates) for k in AccountCategory
    }

    for acct in query.all():
      acct: Account
      _, acct_values, _ = acct.get_value(start, end)
      cat_values = categories[acct.category.name.lower()]
      for i, v in enumerate(acct_values):
        total[i] += v
        cat_values[i] += v

    response = {"total": total, "categories": categories, "dates": dates}
    if request_args is not None:
      return response
    return flask.jsonify(response)


def get_value_by_asset() -> flask.Response:
  """GET /api/portfolio/value-by-asset

  Returns:
    JSON response, see api.yaml for details
  """
  with flask.current_app.app_context():
    p: portfolio.Portfolio = flask.current_app.portfolio
  today = datetime.date.today()

  args: t.JSONObj = flask.request.args.to_dict()
  start = web_common.parse_date(args.get("start", today))
  end = web_common.parse_date(args.get("end", today))
  category = web_common.parse_enum(args.get("category"), AssetCategory)
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    q_accts = s.query(Account)

    q_assets = s.query(Asset.uuid)
    if category is not None:
      q_assets = q_assets.where(Asset.category == category)
    allowed_assets: t.Strings = [uuid for uuid, in q_assets.all()]

    # Prepare dates
    dates: t.Dates = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    assets: t.DictReals = {}

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
    request_args: t.JSONObj = None) -> t.Union[flask.Response, t.JSONObj]:
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

  start = web_common.parse_date(args.get("start", today))
  end = web_common.parse_date(args.get("end", today))
  category = web_common.parse_enum(args.get("category"), AccountCategory)
  integrate = bool(args.get("integrate", False))
  if end < start:
    raise HTTPError(422, detail="End date must be on or after Start date")

  with p.get_session() as s:
    query = s.query(Account)
    if category is not None:
      query = query.where(Account.category == category)

    # Prepare dates
    dates: t.Dates = []
    date = start
    while date <= end:
      dates.append(date)
      date += datetime.timedelta(days=1)

    categories: t.Dict[TransactionCategory, t.Reals] = {
        cat: [Decimal(0)] * len(dates) for cat in TransactionCategory
    }
    categories["unknown-inflow"] = [Decimal(0)] * len(
        dates)  # Category is nullable
    categories["unknown-outflow"] = [Decimal(0)] * len(
        dates)  # Category is nullable

    for acct in query.all():
      acct: Account
      _, acct_categories = acct.get_cash_flow(start, end)
      for cat, values in acct_categories.items():
        values_sum = categories[cat]
        for i, v in enumerate(values):
          values_sum[i] += v

    if integrate:
      for cat, values in categories.items():
        integral = Decimal(0)
        for i, v in enumerate(values):
          integral += v
          values[i] = integral

    total = [Decimal(0)] * len(dates)
    inflow = [Decimal(0)] * len(dates)
    outflow = [Decimal(0)] * len(dates)
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

  args: t.JSONObj = flask.request.args.to_dict()
  integrate = bool(args.get("integrate", False))

  result = get_cash_flow(request_args=args)

  to_skip = ["income", "transfer", "instrument", "unknown-inflow"]

  outflow: t.Reals = result["outflow"]
  outflow_categorized: t.DictReals = {
      cat: v for cat, v in result["categories"].items() if cat not in to_skip
  }
  dates: t.Dates = result["dates"]
  start = dates[0]
  end = dates[-1]

  target_categorized: t.DictReals = {
      cat: [] for cat in outflow_categorized if cat != "unknown-outflow"
  }

  with p.get_session() as s:
    query = s.query(Budget).order_by(Budget.date)

    date = start

    current_categories = {cat: Decimal(0) for cat in target_categorized}
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
  daily_factor = Decimal(0)
  factors = []
  for date in dates:
    if date.month != current_month:
      current_month = date.month
      month_len = calendar.monthrange(date.year, date.month)[1]
      # Daily budget = (annual budget) / (12 months) / (days in month)
      # So the sum(budget[any single month]) = annual / 12
      daily_factor = 1 / Decimal(12 * month_len)
    factors.append(daily_factor)

  for cat, values in target_categorized.items():
    target_categorized[cat] = [v * f for v, f in zip(values, factors)]

  if integrate:
    for cat, values in target_categorized.items():
      integral = Decimal(0)
      for i, v in enumerate(values):
        integral += v
        values[i] = integral

  # Sum for total
  target = [Decimal(0)] * len(dates)
  for cat, values in target_categorized.items():
    for i, v in enumerate(values):
      target[i] += v

  # Use round_list to limit response precision whilst maintaining
  # sum(list) = sum(round_list)

  response = {
      "outflow": outflow,
      "outflow_categorized": outflow_categorized,
      "target": common.round_list(target),
      "target_categorized": {
          cat: common.round_list(values)
          for cat, values in target_categorized.items()
      },
      "dates": dates
  }

  return flask.jsonify(response)


def get_emergency_fund() -> flask.Response:
  """GET /api/portfolio/emergency-fund

  Returns:
    JSON response, see api.yaml for details
  """
  today = datetime.date.today()

  args: t.JSONObj = flask.request.args.to_dict()
  start = web_common.parse_date(args.get("start", today))
  end = web_common.parse_date(args.get("end", today))
  lower = int(args.get("lower", 92))  # 3 months
  upper = int(args.get("upper", 183))  # 6 months

  result = get_value_by_category(request_args={"start": start, "end": end})
  actual_balance: t.Reals = result["categories"]["cash"]
  dates: t.Dates = result["dates"]

  result = get_cash_flow(request_args={
      "start": start - datetime.timedelta(days=upper),
      "end": end
  })
  # Emergency spending categories
  # TODO (WattsUp) Replace with is_essential
  # Possibly combined with budget?
  to_keep = ["home", "food", "services"]
  outflow_categorized: t.DictReals = {
      cat: v for cat, v in result["categories"].items() if cat in to_keep
  }
  outflow: t.Reals = [sum(x) for x in zip(*outflow_categorized.values())]
  cash_flow_dates: t.Dates = result["dates"]

  lower_balance: t.Reals = []
  upper_balance: t.Reals = []

  current_lower: t.Reals = []
  current_upper: t.Reals = []
  for i, date in enumerate(cash_flow_dates):
    current_lower.append(outflow[i])
    current_upper.append(outflow[i])
    if len(current_lower) > lower:
      current_lower.pop(0)
    if len(current_upper) > upper:
      current_lower.pop(0)
    if date >= start:
      lower_balance.append(sum(current_lower))
      upper_balance.append(sum(current_upper))

  response = {
      "actual_balance": actual_balance,
      "lower_balance": lower_balance,
      "upper_balance": upper_balance,
      "dates": dates
  }
  return flask.jsonify(response)
