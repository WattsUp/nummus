"""Test module nummus.web.controller_portfolio
"""

import datetime
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           AssetValuation, Transaction, TransactionCategory,
                           TransactionSplit)

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
                          total=self._RNG.uniform(-10, -1),
                          statement=self.random_string())
        t_split = TransactionSplit(total=txn.total, parent=txn)
        s.add_all((txn, t_split))

      for _ in range(n_transactions):
        txn = Transaction(account=acct_savings,
                          date=today,
                          total=self._RNG.uniform(-10, 10),
                          statement=self.random_string())
        t_split_0 = TransactionSplit(total=txn.total, parent=txn)
        t_split_1 = TransactionSplit(total=txn.total,
                                     parent=txn,
                                     asset=a_apple,
                                     asset_quantity=self._RNG.uniform(
                                         0.001, 0.01))
        s.add_all((txn, t_split_0, t_split_1))

      for _ in range(n_transactions):
        txn = Transaction(account=acct_invest,
                          date=today,
                          total=self._RNG.uniform(-10, -1),
                          statement=self.random_string())
        t_split_0 = TransactionSplit(total=txn.total,
                                     parent=txn,
                                     asset=a_banana,
                                     asset_quantity=self._RNG.uniform(
                                         100, 1000))
        t_split_1 = TransactionSplit(total=txn.total,
                                     parent=txn,
                                     asset=a_apple,
                                     asset_quantity=self._RNG.uniform(
                                         100, 1000))
        s.add_all((txn, t_split_0, t_split_1))
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
    self.assertEqualWithinError(target, result, 1e-6)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "total": [0, total],
        "assets": [0, assets],
        "liabilities": [0, liabilities],
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)

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
    self.assertEqualWithinError(target, result, 1e-6)

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
    self.assertEqualWithinError(target, result, 1e-6)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "total": [0, total],
        "accounts": {
            k: [0, v] for k, v in accounts.items()
        },
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)

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
    self.assertEqualWithinError(target, result, 1e-6)

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
    self.assertEqualWithinError(target, result, 1e-6)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "total": [0, total],
        "categories": {
            k: [0, v] for k, v in categories.items()
        },
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)

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
    self.assertEqualWithinError(target, result, 1e-6)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "assets": {
            k: [0, v] for k, v in assets.items()
        },
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)

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
    self.assertEqualWithinError(target, result, 1e-6)

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

    # All assets
    with p.get_session() as s:
      categories = {cat: 0 for cat in TransactionCategory}
      categories[None] = 0

      q = s.query(Account)
      for acct in q.all():
        _, acct_categories = acct.get_cash_flow(today, today)
        for cat, v in acct_categories.items():
          categories[cat] += v[0]

      total = sum(categories.values())

    endpoint = "/api/portfolio/cash-flow"

    def enum_to_str(e: TransactionCategory) -> str:
      if e is None:
        return "none"
      return e.name.lower()

    result, _ = self.api_get(endpoint)
    target = {
        "total": [total],
        "categories": {
            enum_to_str(cat): [v] for cat, v in categories.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": tomorrow})
    target = {
        "total": [0, total, 0],
        "categories": {
            enum_to_str(cat): [0, v, 0] for cat, v in categories.items()
        },
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat()
        ]
    }
    self.assertEqualWithinError(target, result, 1e-6)

    result, _ = self.api_get(endpoint, {
        "start": yesterday,
        "end": tomorrow,
        "integrate": True
    })
    target = {
        "total": [0, total, total],
        "categories": {
            enum_to_str(cat): [0, v, v] for cat, v in categories.items()
        },
        "dates": [
            yesterday.isoformat(),
            today.isoformat(),
            tomorrow.isoformat()
        ]
    }
    self.assertEqualWithinError(target, result, 1e-6)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Invalid date format
    self.api_get(endpoint, {"start": self.random_string()}, rc=400)

    # Just cash Accounts
    with p.get_session() as s:
      categories = {cat: 0 for cat in TransactionCategory}
      categories[None] = 0

      q = s.query(Account).where(Account.category == AccountCategory.CASH)
      for acct in q.all():
        _, acct_categories = acct.get_cash_flow(today, today)
        for cat, v in acct_categories.items():
          categories[cat] += v[0]

      total = sum(categories.values())

    result, _ = self.api_get(endpoint, {"category": "cash"})
    target = {
        "total": [total],
        "categories": {
            enum_to_str(cat): [v] for cat, v in categories.items()
        },
        "dates": [today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)