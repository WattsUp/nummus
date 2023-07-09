"""Test module nummus.web.controller_portfolio
"""

import datetime
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           AssetValuation, Transaction, TransactionSplit)

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
      asset = Asset(name="BANANA", category=AssetCategory.SECURITY)
      s.add_all((acct_checking, acct_savings, acct_invest, asset))
      s.commit()

      v = AssetValuation(asset=asset, date=today, value=1)
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
        t_split = TransactionSplit(total=txn.total, parent=txn)
        s.add_all((txn, t_split))

      for _ in range(n_transactions):
        txn = Transaction(account=acct_invest,
                          date=today,
                          total=self._RNG.uniform(-10, -1),
                          statement=self.random_string())
        t_split = TransactionSplit(total=txn.total,
                                   parent=txn,
                                   asset=asset,
                                   asset_quantity=self._RNG.uniform(100, 1000))
        s.add_all((txn, t_split))
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

    result, _ = self.api_get(endpoint, {"account_category": "cash"})
    target = {
        "total": [total],
        "assets": [assets],
        "liabilities": [liabilities],
        "dates": [today.isoformat()]
    }
    self.assertEqualWithinError(target, result, 1e-6)
