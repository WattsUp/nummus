"""Test module nummus.web.common
"""

import datetime
import uuid

import connexion

from nummus import portfolio
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Transaction, TransactionSplit)
from nummus.web import common

from tests.base import TestBase


class TestCommon(TestBase):
  """Test web common methods
  """

  def test_find_account(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)

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

      # Bad UUID
      self.assertRaises(connexion.exceptions.BadRequestProblem,
                        common.find_account, s, self.random_string())

  def test_find_asset(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)

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

      # Account does not exist
      with self.assertRaises(connexion.exceptions.ProblemException) as cm:
        common.find_asset(s, str(uuid.uuid4()))
      e: connexion.exceptions.ProblemException = cm.exception
      self.assertEqual(404, e.status)

      # Bad UUID
      self.assertRaises(connexion.exceptions.BadRequestProblem,
                        common.find_asset, s, self.random_string())

  def test_find_transaction(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)

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

      # Bad UUID
      self.assertRaises(connexion.exceptions.BadRequestProblem,
                        common.find_transaction, s, self.random_string())
