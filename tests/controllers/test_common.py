"""Test module nummus.controllers.common
"""

import datetime
from decimal import Decimal

from nummus.models import (Account, AccountCategory, Transaction,
                           TransactionSplit)
from nummus.controllers import common

from tests.controllers.base import WebTestBase


class TestCommon(WebTestBase):
  """Test common components controller
  """

  def test_sidebar(self):
    p = self._portfolio

    today = datetime.date.today()

    with self._flask_app.app_context():
      result = common.sidebar()
    target = {
        "net-worth": Decimal(0),
        "assets": Decimal(0),
        "liabilities": Decimal(0),
        "assets-w": 0,
        "liabilities-w": 0,
        "categories": {}
    }
    self.assertDictEqual(target, result)

    with p.get_session() as s:
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      acct_savings = Account(name="Monkey Bank Savings",
                             institution="Monkey Bank",
                             category=AccountCategory.CASH)
      s.add_all((acct_checking, acct_savings))
      s.commit()

      txn = Transaction(account=acct_savings,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=txn.total, parent=txn)
      s.add_all((txn, t_split))

      txn = Transaction(account=acct_checking,
                        date=today,
                        total=-50,
                        statement=self.random_string())
      t_split = TransactionSplit(total=txn.total, parent=txn)
      s.add_all((txn, t_split))

      s.commit()

    target_accounts = [{
        "institution": "Monkey Bank",
        "name": "Monkey Bank Checking",
        "updated_days_ago": 0,
        "value": Decimal("-50.000000"),
        "category": AccountCategory.CASH
    }, {
        "institution": "Monkey Bank",
        "name": "Monkey Bank Savings",
        "updated_days_ago": 0,
        "value": Decimal("100.000000"),
        "category": AccountCategory.CASH
    }]
    target = {
        "net-worth": Decimal("50.000000"),
        "assets": Decimal("100.000000"),
        "liabilities": Decimal("-50.000000"),
        "assets-w": Decimal("66.67"),
        "liabilities-w": Decimal("33.33"),
        "categories": {
            AccountCategory.CASH: (Decimal("50.000000"), target_accounts)
        }
    }
    with self._flask_app.app_context():
      result = common.sidebar()
    self.assertDictEqual(target, result)
