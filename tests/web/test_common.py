"""Test module nummus.web.common
"""

import datetime
import uuid

import flask

from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Budget, Transaction, TransactionSplit)
from nummus.web import common

from tests.web.base import WebTestBase


class TestCommon(WebTestBase):
  """Test web common methods
  """

  def test_find_account(self):
    p = self._portfolio

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = str(a.uuid)
      result = common.find_account(s, a_uuid)
      self.assertEqual(a, result)

      # Get by uuid without dashes
      result = common.find_account(s, a_uuid.replace("-", ""))
      self.assertEqual(a, result)

      # Account does not exist
      self.assertHTTPRaises(404, common.find_account, s, str(uuid.uuid4()))

  def test_find_asset(self):
    p = self._portfolio

    # Create asset
    a = Asset(name="Banana", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = str(a.uuid)
      result = common.find_asset(s, a_uuid)
      self.assertEqual(a, result)

      # Get by uuid without dashes
      result = common.find_asset(s, a_uuid.replace("-", ""))
      self.assertEqual(a, result)

      # Asset does not exist
      self.assertHTTPRaises(404, common.find_asset, s, str(uuid.uuid4()))

  def test_find_budget(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = str(b.uuid)
      result = common.find_budget(s, b_uuid)
      self.assertEqual(b, result)

      # Get by uuid without dashes
      result = common.find_budget(s, b_uuid.replace("-", ""))
      self.assertEqual(b, result)

      # Budget does not exist
      self.assertHTTPRaises(404, common.find_budget, s, str(uuid.uuid4()))

  def test_find_transaction(self):
    p = self._portfolio

    # Create accounts and transactions
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      t = Transaction(account_id=a.id,
                      date=today,
                      total=100,
                      statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=t)
      s.add_all((t, t_split))
      s.commit()

      t_uuid = str(t.uuid)
      result = common.find_transaction(s, t_uuid)
      self.assertEqual(t, result)

      # Get by uuid without dashes
      result = common.find_transaction(s, t_uuid.replace("-", ""))
      self.assertEqual(t, result)

      # Transaction does not exist
      self.assertHTTPRaises(404, common.find_transaction, s, str(uuid.uuid4()))

  def test_parse_uuid(self):
    target = uuid.uuid4()
    s = str(target)
    result = common.parse_uuid(s)
    self.assertEqual(target, result)

    s = str(target).replace("-", "")
    result = common.parse_uuid(s)
    self.assertEqual(target, result)

    result = common.parse_uuid(target)
    self.assertEqual(target, result)

    result = common.parse_uuid(None)
    self.assertIsNone(result)

    # Bad UUID
    self.assertHTTPRaises(400, common.parse_uuid, self.random_string())

  def test_parse_date(self):
    target = datetime.date.today()
    s = target.isoformat()
    result = common.parse_date(s)
    self.assertEqual(target, result)

    result = common.parse_date(target)
    self.assertEqual(target, result)

    result = common.parse_date(None)
    self.assertIsNone(result)

    # Bad Date
    self.assertHTTPRaises(400, common.parse_date, self.random_string())

  def test_parse_enum(self):
    target: AccountCategory = self._RNG.choice(AccountCategory)
    s = target.name.lower()
    result = common.parse_enum(s, AccountCategory)
    self.assertEqual(target, result)

    result = common.parse_enum(target, AccountCategory)
    self.assertEqual(target, result)

    result = common.parse_enum(None, AccountCategory)
    self.assertIsNone(result)

    # Bad Enum
    self.assertHTTPRaises(400, common.parse_enum, self.random_string(),
                          AccountCategory)

  def test_search(self):
    # Bulk of search testing happens in the appropriate controller tests
    p = self._portfolio

    # Create accounts
    a_checking = Account(name="Monkey Bank Checking",
                         institution="Monkey Bank",
                         category=AccountCategory.CASH)
    a_invest = Account(name="Monkey Investments",
                       institution="Ape Trading",
                       category=AccountCategory.INVESTMENT)
    with p.get_session() as s:
      s.add_all((a_checking, a_invest))
      s.commit()

      query = s.query(Account)

      # Unknown Model
      self.assertRaises(KeyError, common.search, s, query, None, "abc")

      # No results return all
      result = common.search(s, query, Account, None).all()
      self.assertEqual([a_checking, a_invest], result)

      # Short query return all
      result = common.search(s, query, Account, "ab").all()
      self.assertEqual([a_checking, a_invest], result)

      # No matches return first 5
      result = common.search(s, query, Account, "crazy unrelated words").all()
      self.assertEqual([a_checking, a_invest], result)

      result = common.search(s, query, Account, "checking").all()
      self.assertEqual([a_checking], result)

      result = common.search(s, query, Account, "bank").all()
      self.assertEqual([a_checking], result)

      result = common.search(s, query, Account, "monkey").all()
      self.assertEqual([a_checking, a_invest], result)

      result = common.search(s, query, Account, "trading").all()
      self.assertEqual([a_invest], result)

  def test_paginate(self):
    p = self._portfolio

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    n_transactions = 10
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      for _ in range(n_transactions):
        t = Transaction(account_id=a.id,
                        date=today,
                        total=100,
                        statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=t)
        s.add_all((t, t_split))
      s.commit()

      query = s.query(Transaction)
      transactions = query.all()

      page, count, next_offset = common.paginate(query, 50, 0)
      self.assertEqual(transactions, page)
      self.assertEqual(n_transactions, count)
      self.assertIsNone(next_offset)

      page, count, next_offset = common.paginate(query, 3, 0)
      self.assertEqual(transactions[0:3], page)
      self.assertEqual(n_transactions, count)
      self.assertEqual(3, next_offset)

      page, count, next_offset = common.paginate(query, 3, 3)
      self.assertEqual(transactions[3:6], page)
      self.assertEqual(n_transactions, count)
      self.assertEqual(6, next_offset)

      page, count, next_offset = common.paginate(query, 3, 6)
      self.assertEqual(transactions[6:9], page)
      self.assertEqual(n_transactions, count)
      self.assertEqual(9, next_offset)

      page, count, next_offset = common.paginate(query, 3, 9)
      self.assertEqual(transactions[9:], page)
      self.assertEqual(n_transactions, count)
      self.assertIsNone(next_offset)

      page, count, next_offset = common.paginate(query, 3, 1000)
      self.assertEqual([], page)
      self.assertEqual(n_transactions, count)
      self.assertIsNone(next_offset)

      page, count, next_offset = common.paginate(query, 3, -1000)
      self.assertEqual(transactions[0:3], page)
      self.assertEqual(n_transactions, count)
      self.assertEqual(3, next_offset)

  def test_validate_image_upload(self):
    # Missing length
    req = flask.Request({})
    self.assertHTTPRaises(411, common.validate_image_upload, req)

    # Still missing type
    req = flask.Request({"CONTENT_LENGTH": "1000001"})
    self.assertHTTPRaises(422, common.validate_image_upload, req)

    # Still bad type
    req = flask.Request({
        "CONTENT_TYPE": "application/pdf",
        "CONTENT_LENGTH": "1000001"
    })
    self.assertHTTPRaises(415, common.validate_image_upload, req)

    # Still bad type
    req = flask.Request({
        "CONTENT_TYPE": "image/pdf",
        "CONTENT_LENGTH": "1000001"
    })
    self.assertHTTPRaises(415, common.validate_image_upload, req)

    # Still too long
    req = flask.Request({
        "CONTENT_TYPE": "image/png",
        "CONTENT_LENGTH": "1000001"
    })
    self.assertHTTPRaises(413, common.validate_image_upload, req)

    # All good
    req = flask.Request({
        "CONTENT_TYPE": "image/png",
        "CONTENT_LENGTH": "1000000"
    })
    suffix = common.validate_image_upload(req)
    self.assertEqual(".png", suffix)
