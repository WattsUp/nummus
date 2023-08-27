"""Test module nummus.models.utils
"""

import datetime

from nummus import models
from nummus.models import (utils, Account, AccountCategory, Transaction,
                           TransactionSplit)

from tests.base import TestBase


class TestUtils(TestBase):
  """Test utility methods
  """

  def test_search(self):
    s = self.get_session()
    models.metadata_create_all(s)

    # Create accounts
    acct_checking = Account(name="Monkey Bank Checking",
                            institution="Monkey Bank",
                            category=AccountCategory.CASH)
    acct_invest = Account(name="Gorilla Investments",
                          institution="Ape Trading",
                          category=AccountCategory.INVESTMENT)
    s.add_all((acct_checking, acct_invest))
    s.commit()

    query = s.query(Account)

    # Unknown Model
    self.assertRaises(KeyError, utils.search, query, None, "abc")

    # No results return all
    result = utils.search(query, Account, None).all()
    self.assertEqual([acct_checking, acct_invest], result)

    # Short query return all
    result = utils.search(query, Account, "ab").all()
    self.assertEqual([acct_checking, acct_invest], result)

    # No matches return first 5
    result = utils.search(query, Account, "crazy unrelated words").all()
    self.assertEqual([acct_checking, acct_invest], result)

    result = utils.search(query, Account, "checking").all()
    self.assertEqual([acct_checking], result)

    result = utils.search(query, Account, "Monkey Bank").all()
    self.assertEqual([acct_checking], result)

    result = utils.search(query, Account, "monkey gorilla").all()
    self.assertEqual([acct_checking, acct_invest], result)

    result = utils.search(query, Account, "trading").all()
    self.assertEqual([acct_invest], result)

  def test_paginate(self):
    s = self.get_session()
    models.metadata_create_all(s)

    n_transactions = 10
    today = datetime.date.today()

    # Create accounts
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH)
    s.add(acct)
    s.commit()

    for _ in range(n_transactions):
      txn = Transaction(account=acct,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=txn)
      s.add_all((txn, t_split))
    s.commit()

    query = s.query(Transaction)
    transactions = query.all()
    query = s.query(Transaction)

    page, count, next_offset = utils.paginate(query, 50, 0)
    self.assertEqual(transactions, page)
    self.assertEqual(n_transactions, count)
    self.assertIsNone(next_offset)

    page, count, next_offset = utils.paginate(query, 3, 0)
    self.assertEqual(transactions[0:3], page)
    self.assertEqual(n_transactions, count)
    self.assertEqual(3, next_offset)

    page, count, next_offset = utils.paginate(query, 3, 3)
    self.assertEqual(transactions[3:6], page)
    self.assertEqual(n_transactions, count)
    self.assertEqual(6, next_offset)

    page, count, next_offset = utils.paginate(query, 3, 6)
    self.assertEqual(transactions[6:9], page)
    self.assertEqual(n_transactions, count)
    self.assertEqual(9, next_offset)

    page, count, next_offset = utils.paginate(query, 3, 9)
    self.assertEqual(transactions[9:], page)
    self.assertEqual(n_transactions, count)
    self.assertIsNone(next_offset)

    page, count, next_offset = utils.paginate(query, 3, 1000)
    self.assertEqual([], page)
    self.assertEqual(n_transactions, count)
    self.assertIsNone(next_offset)

    page, count, next_offset = utils.paginate(query, 3, -1000)
    self.assertEqual(transactions[0:3], page)
    self.assertEqual(n_transactions, count)
    self.assertEqual(3, next_offset)