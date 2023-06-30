"""Test module nummus.web.common
"""

import datetime
import uuid

import connexion

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
      with self.assertRaises(connexion.exceptions.ProblemException) as cm:
        common.find_account(s, str(uuid.uuid4()))
      e: connexion.exceptions.ProblemException = cm.exception
      self.assertEqual(404, e.status)

  def test_find_asset(self):
    p = self._portfolio

    # Create asset
    a = Asset(name="Monkey Bank Checking", category=AssetCategory.ITEM)
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
      with self.assertRaises(connexion.exceptions.ProblemException) as cm:
        common.find_asset(s, str(uuid.uuid4()))
      e: connexion.exceptions.ProblemException = cm.exception
      self.assertEqual(404, e.status)

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
      with self.assertRaises(connexion.exceptions.ProblemException) as cm:
        common.find_budget(s, str(uuid.uuid4()))
      e: connexion.exceptions.ProblemException = cm.exception
      self.assertEqual(404, e.status)

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
      with self.assertRaises(connexion.exceptions.ProblemException) as cm:
        common.find_transaction(s, str(uuid.uuid4()))
      e: connexion.exceptions.ProblemException = cm.exception
      self.assertEqual(404, e.status)

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
    self.assertRaises(connexion.exceptions.BadRequestProblem, common.parse_uuid,
                      self.random_string())

  def test_parse_date(self):
    target = datetime.date.today()
    s = target.isoformat()
    result = common.parse_date(s)
    self.assertEqual(target, result)

    result = common.parse_date(target)
    self.assertEqual(target, result)

    result = common.parse_date(None)
    self.assertIsNone(result)

    # Bad UUID
    self.assertRaises(connexion.exceptions.BadRequestProblem, common.parse_date,
                      self.random_string())

  def test_parse_enum(self):
    target: AccountCategory = self._RNG.choice(AccountCategory)
    s = target.name.lower()
    result = common.parse_enum(s, AccountCategory)
    self.assertEqual(target, result)

    result = common.parse_enum(target, AccountCategory)
    self.assertEqual(target, result)

    result = common.parse_enum(None, AccountCategory)
    self.assertIsNone(result)

    # Bad UUID
    self.assertRaises(connexion.exceptions.BadRequestProblem, common.parse_enum,
                      self.random_string(), AccountCategory)
