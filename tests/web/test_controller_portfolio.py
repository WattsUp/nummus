"""Test module nummus.web.controller_portfolio
"""

import calendar
import datetime
from decimal import Decimal

from nummus import common
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           AssetValuation, Budget, Transaction,
                           TransactionCategory, TransactionSplit)

from tests.web.base import WebTestBase


class TestControllerPortfolio(WebTestBase):
  """Test controller_portfolio methods
  """

  def prepare_portfolio(self):
    """Create a test portfolio
    """
    p = self._portfolio

    n_transactions = 10
    today = datetime.date.today()
    with p.get_session() as s:
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      acct_savings = Account(name="Monkey Bank Savings",
                             institution="Monkey Bank",
                             category=AccountCategory.CASH)
      acct_invest = Account(name="Monkey Investments",
                            institution="Monkey Bank",
                            category=AccountCategory.INVESTMENT)
      a_banana = Asset(name="BANANA", category=AssetCategory.SECURITY)
      a_apple = Asset(name="Apple", category=AssetCategory.ITEM)
      s.add_all((acct_checking, acct_savings, acct_invest, a_banana, a_apple))
      s.commit()

      v = AssetValuation(asset=a_banana, date=today, value=1)
      s.add(v)

      v = AssetValuation(asset=a_apple, date=today, value=1)
      s.add(v)

      for _ in range(n_transactions):
        txn = Transaction(account=acct_checking,
                          date=today,
                          total=self.random_decimal(-10, -1),
                          statement=self.random_string())
        t_split = TransactionSplit(total=txn.total, parent=txn)
        s.add_all((txn, t_split))

      for _ in range(n_transactions):
        txn = Transaction(account=acct_savings,
                          date=today,
                          total=self.random_decimal(1, 10),
                          statement=self.random_string())
        t_split_0 = TransactionSplit(total=txn.total, parent=txn)
        t_split_1 = TransactionSplit(total=txn.total,
                                     parent=txn,
                                     asset=a_apple,
                                     asset_quantity=self.random_decimal(
                                         0.001, 0.01))
        s.add_all((txn, t_split_0, t_split_1))

      for _ in range(n_transactions):
        txn = Transaction(account=acct_invest,
                          date=today,
                          total=self.random_decimal(-10, -1),
                          statement=self.random_string())
        t_split_0 = TransactionSplit(total=txn.total,
                                     parent=txn,
                                     asset=a_banana,
                                     asset_quantity=self.random_decimal(
                                         100, 1000))
        t_split_1 = TransactionSplit(total=txn.total,
                                     parent=txn,
                                     asset=a_apple,
                                     asset_quantity=self.random_decimal(
                                         100, 1000))
        s.add_all((txn, t_split_0, t_split_1))

      b = Budget(date=today,
                 home=self.random_decimal(-100, 0),
                 food=self.random_decimal(-100, 0),
                 shopping=self.random_decimal(-100, 0),
                 hobbies=self.random_decimal(-100, 0),
                 services=self.random_decimal(-100, 0),
                 travel=self.random_decimal(-100, 0))
      s.add(b)

      b = Budget(date=today + datetime.timedelta(days=2),
                 home=self.random_decimal(-100, 0),
                 food=self.random_decimal(-100, 0),
                 shopping=self.random_decimal(-100, 0),
                 hobbies=self.random_decimal(-100, 0),
                 services=self.random_decimal(-100, 0),
                 travel=self.random_decimal(-100, 0))
      s.add(b)
      s.commit()

  def test_get_value(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    with p.get_session() as s:
      assets = 0
      liabilities = 0

      q = s.query(Account)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        value = values[0]
        if value > 0:
          assets += value
        else:
          liabilities += value
      total = assets + liabilities

    endpoint = "/api/portfolio/value"

    result, _ = self.api_get(endpoint)
    target = {
        "total": [total],
        "assets": [assets],
        "liabilities": [liabilities],
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "total": [0, total],
        "assets": [0, assets],
        "liabilities": [0, liabilities],
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertDictEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

    # Just cash Accounts
    with p.get_session() as s:
      assets = 0
      liabilities = 0

      q = s.query(Account).where(Account.category == AccountCategory.CASH)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        value = values[0]
        if value > 0:
          assets += value
        else:
          liabilities += value
      total = assets + liabilities

    result, _ = self.api_get(endpoint, {"category": "cash"})
    target = {
        "total": [total],
        "assets": [assets],
        "liabilities": [liabilities],
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

  def test_get_value_by_account(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    with p.get_session() as s:
      total = 0
      accounts = {}

      q = s.query(Account)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        value = values[0]
        accounts[acct.uuid] = value
        total += value

    endpoint = "/api/portfolio/value-by-account"

    result, _ = self.api_get(endpoint)
    target = {
        "total": [total],
        "accounts": {
            k: [v] for k, v in accounts.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "total": [0, total],
        "accounts": {
            k: [0, v] for k, v in accounts.items()
        },
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertDictEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

    # Just cash Accounts
    with p.get_session() as s:
      total = 0
      accounts = {}

      q = s.query(Account).where(Account.category == AccountCategory.CASH)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        value = values[0]
        accounts[acct.uuid] = value
        total += value

    result, _ = self.api_get(endpoint, {"category": "cash"})
    target = {
        "total": [total],
        "accounts": {
            k: [v] for k, v in accounts.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

  def test_get_value_by_category(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    with p.get_session() as s:
      total = 0
      categories = {k.name.lower(): 0 for k in AccountCategory}

      q = s.query(Account).where(Account.category == AccountCategory.CASH)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        value = values[0]
        categories["cash"] += value
        total += value

      q = s.query(Account).where(Account.category == AccountCategory.INVESTMENT)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        value = values[0]
        categories["investment"] += value
        total += value

    endpoint = "/api/portfolio/value-by-category"

    result, _ = self.api_get(endpoint)
    target = {
        "total": [total],
        "categories": {
            k: [v] for k, v in categories.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "total": [0, total],
        "categories": {
            k: [0, v] for k, v in categories.items()
        },
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertDictEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

  def test_get_value_by_asset(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    # All assets
    with p.get_session() as s:
      assets = {}

      q = s.query(Account)
      for acct in q.all():
        _, _, acct_assets = acct.get_value(today, today)
        for a, a_values in acct_assets.items():
          if a not in assets:
            assets[a] = a_values[0]
          else:
            assets[a] += a_values[0]

    endpoint = "/api/portfolio/value-by-asset"

    result, _ = self.api_get(endpoint)
    target = {
        "assets": {
            k: [v] for k, v in assets.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "assets": {
            k: [0, v] for k, v in assets.items()
        },
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertDictEqual(target, result)

    # Only SECURITIES
    with p.get_session() as s:
      assets = {}

      q = s.query(Account)
      for acct in q.all():
        _, _, acct_assets = acct.get_value(today, today)
        for a, a_values in acct_assets.items():
          asset = s.query(Asset).where(Asset.uuid == a).first()
          if asset.category != AssetCategory.SECURITY:
            continue
          if a not in assets:
            assets[a] = a_values[0]
          else:
            assets[a] += a_values[0]

    endpoint = "/api/portfolio/value-by-asset"

    result, _ = self.api_get(endpoint, {"category": "security"})
    target = {
        "assets": {
            k: [v] for k, v in assets.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

  def test_get_cash_flow(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)

    # All accounts
    with p.get_session() as s:
      categories = {cat: 0 for cat in TransactionCategory}
      categories["unknown-inflow"] = 0
      categories["unknown-outflow"] = 0

      q = s.query(Account)
      for acct in q.all():
        _, acct_categories = acct.get_cash_flow(today, today)
        for cat, v in acct_categories.items():
          categories[cat] += v[0]

      total = sum(categories.values())
      inflow = sum(v for v in categories.values() if v > 0)
      outflow = sum(v for v in categories.values() if v < 0)

    endpoint = "/api/portfolio/cash-flow"

    def enum_to_str(e: TransactionCategory) -> str:
      if isinstance(e, str):
        return e
      return e.name.lower()

    result, _ = self.api_get(endpoint)
    target = {
        "total": [total],
        "inflow": [inflow],
        "outflow": [outflow],
        "categories": {
            enum_to_str(cat): [v] for cat, v in categories.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": tomorrow})
    target = {
        "total": [0, total, 0],
        "inflow": [0, inflow, 0],
        "outflow": [0, outflow, 0],
        "categories": {
            enum_to_str(cat): [0, v, 0] for cat, v in categories.items()
        },
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat()
        ]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {
        "start": yesterday,
        "end": tomorrow,
        "integrate": True
    })
    target = {
        "total": [0, total, total],
        "inflow": [0, inflow, inflow],
        "outflow": [0, outflow, outflow],
        "categories": {
            enum_to_str(cat): [0, v, v] for cat, v in categories.items()
        },
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat()
        ]
    }
    self.assertDictEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

    # Just cash Accounts
    with p.get_session() as s:
      categories = {cat: 0 for cat in TransactionCategory}
      categories["unknown-inflow"] = 0
      categories["unknown-outflow"] = 0

      q = s.query(Account).where(Account.category == AccountCategory.CASH)
      for acct in q.all():
        _, acct_categories = acct.get_cash_flow(today, today)
        for cat, v in acct_categories.items():
          categories[cat] += v[0]

      total = sum(categories.values())
      inflow = sum(v for v in categories.values() if v > 0)
      outflow = sum(v for v in categories.values() if v < 0)

    result, _ = self.api_get(endpoint, {"category": "cash"})
    target = {
        "total": [total],
        "inflow": [inflow],
        "outflow": [outflow],
        "categories": {
            enum_to_str(cat): [v] for cat, v in categories.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

  def test_get_budget(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    future = today + datetime.timedelta(days=2)

    def enum_to_str(e: TransactionCategory) -> str:
      if isinstance(e, str):
        return e
      return e.name.lower()

    # All assets
    with p.get_session() as s:
      outflow_categorized = {cat: 0 for cat in TransactionCategory}
      outflow_categorized["unknown-inflow"] = 0
      outflow_categorized["unknown-outflow"] = 0

      q = s.query(Account)
      for acct in q.all():
        _, acct_categories = acct.get_cash_flow(today, today)
        for cat, v in acct_categories.items():
          outflow_categorized[cat] += v[0]

      to_skip = ["income", "transfer", "instrument", "unknown-inflow"]
      outflow_categorized = {
          enum_to_str(cat): v
          for cat, v in outflow_categorized.items()
          if enum_to_str(cat) not in to_skip
      }
      outflow = sum(outflow_categorized.values())

      b_today = s.query(Budget).order_by(Budget.date).first()
      b_future = s.query(Budget).order_by(Budget.date.desc()).first()

      d = b_today.date
      month_len_today = calendar.monthrange(d.year, d.month)[1]
      d = b_future.date
      month_len_future = calendar.monthrange(d.year, d.month)[1]

      daily_factor_today = 1 / Decimal(12 * month_len_today)
      daily_factor_future = 1 / Decimal(12 * month_len_future)

      budget_categorized_today = {
          enum_to_str(cat): v * daily_factor_today
          for cat, v in b_today.categories.items()
          if enum_to_str(cat) not in to_skip
      }
      budget_today = sum(budget_categorized_today.values())

      budget_categorized_future = {
          enum_to_str(cat): v * daily_factor_future
          for cat, v in b_future.categories.items()
          if enum_to_str(cat) not in to_skip
      }
      budget_future = sum(budget_categorized_future.values())
      budget_future_annual = b_future.total

    endpoint = "/api/portfolio/budget"

    result, _ = self.api_get(endpoint)
    target = {
        "outflow": [outflow],
        "outflow_categorized": {
            cat: [v] for cat, v in outflow_categorized.items()
        },
        "target": common.round_list([budget_today]),
        "target_categorized": {
            cat: common.round_list([v])
            for cat, v in budget_categorized_today.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": future})
    target = {
        "outflow": [Decimal(0), outflow,
                    Decimal(0), Decimal(0)],
        "outflow_categorized": {
            cat: [Decimal(0), v, Decimal(0),
                  Decimal(0)] for cat, v in outflow_categorized.items()
        },
        "target":
            common.round_list([0, budget_today, budget_today, budget_future]),
        "target_categorized": {
            cat: common.round_list([0, v0, v0, v1])
            for cat, v0, v1 in zip(budget_categorized_today.keys(),
                                   budget_categorized_today.values(),
                                   budget_categorized_future.values())
        },
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat(),
            future.isoformat()
        ]
    }
    self.assertDictEqual(target, result)

    # Validate sum(month) == annual / 12
    next_month = datetime.date(future.year + ((future.month + 1) // 12),
                               future.month % 12 + 1, 1)
    eom = datetime.date(
        next_month.year, next_month.month,
        calendar.monthrange(next_month.year, next_month.month)[1])
    result, _ = self.api_get(endpoint, {"start": next_month, "end": eom})
    self.assertEqual(round(budget_future_annual / 12, 6), sum(result["target"]))

    # Validate sum(year) == annual
    next_year = datetime.date(next_month.year + 1, 1, 1)
    eoy = datetime.date(next_month.year + 1, 12, 31)
    result, _ = self.api_get(endpoint, {"start": next_year, "end": eoy})
    self.assertEqual(budget_future_annual, sum(result["target"]))

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

    # Test integration
    result, _ = self.api_get(endpoint, {
        "start": yesterday,
        "end": future,
        "integrate": True
    })
    target = {
        "outflow": [Decimal(0), outflow, outflow, outflow],
        "outflow_categorized": {
            cat: [Decimal(0), v, v, v] for cat, v in outflow_categorized.items()
        },
        "target":
            common.round_list([
                0, budget_today, budget_today + budget_today,
                budget_today + budget_today + budget_future
            ]),
        "target_categorized": {
            cat: common.round_list([0, v0, v0 + v0, v0 + v0 + v1])
            for cat, v0, v1 in zip(budget_categorized_today.keys(),
                                   budget_categorized_today.values(),
                                   budget_categorized_future.values())
        },
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat(),
            future.isoformat()
        ]
    }
    self.assertDictEqual(target, result)

  def test_get_emergency_fund(self):
    p = self._portfolio
    self.prepare_portfolio()
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    future = today + datetime.timedelta(days=2)

    # All accounts
    with p.get_session() as s:
      outflow = 0

      q = s.query(Account)
      for acct in q.all():
        _, acct_categories = acct.get_cash_flow(today, today)
        for cat, v in acct_categories.items():
          if cat in ["home", "food", "services"]:
            outflow += v[0]

      balance = 0

      q = s.query(Account).where(Account.category == AccountCategory.CASH)
      for acct in q.all():
        _, values, _ = acct.get_value(today, today)
        balance += values[0]

    endpoint = "/api/portfolio/emergency-fund"

    result, _ = self.api_get(endpoint)
    target = {
        "actual_balance": [balance],
        "lower_balance": [outflow],
        "upper_balance": [outflow],
        "dates": [today.isoformat()]
    }
    self.assertDictEqual(target, result)

    result, _ = self.api_get(endpoint, {
        "lower": 1,
        "upper": 2,
        "start": yesterday,
        "end": future
    })
    target = {
        "actual_balance": [0, balance, balance, balance],
        "lower_balance": [0, outflow, 0, 0],
        "upper_balance": [0, outflow, outflow, 0],
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat(),
            future.isoformat()
        ]
    }
    self.assertDictEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)
