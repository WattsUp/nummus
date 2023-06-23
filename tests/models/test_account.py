"""Test module nummus.models.account
"""

import datetime

from nummus import models
from nummus.models import account, asset

from tests.base import TestBase


class TestTransaction(TestBase):
  """Test Transaction class
  """

  def test_init_properties(self):
    session = self._get_session()
    models.metadata_create_all(session)

    a = account.Account(name=self.random_string(),
                        institution=self.random_string(),
                        category=account.AccountCategory.CASH)
    session.add(a)
    session.commit()

    asset_bananas = asset.Asset(name="bananas",
                                category=asset.AssetCategory.ITEM)
    session.add(asset_bananas)
    session.commit()

    d = {
        "account_id": a.id,
        "date": datetime.date.today(),
        "total": self._RNG.uniform(-1, 1),
        "statement": self.random_string()
    }

    t = account.Transaction(**d)
    session.add(t)
    session.commit()

    self.assertEqual(d["account_id"], t.account_id)
    self.assertEqual(a, t.account)
    self.assertEqual(d["date"], t.date)
    self.assertEqual(d["total"], t.total)
    self.assertEqual(d["statement"], t.statement)
    self.assertFalse(t.locked)

    d["sales_tax"] = self._RNG.uniform(-1, 0)
    d["payee"] = self.random_string()
    d["description"] = self.random_string()
    d["category"] = account.TransactionCategory.FOOD
    d["subcategory"] = self.random_string()
    d["tag"] = self.random_string()
    d["locked"] = True
    d["asset_id"] = asset_bananas.id
    d["asset_quantity"] = self._RNG.uniform(-1, 1)
    d["parent_id"] = t.id

    t_split = account.Transaction(**d)
    session.add(t_split)
    session.commit()

    # Test default and hidden properties
    d["id"] = t_split.id
    result = t_split.to_dict()
    self.assertDictEqual(d, result)

    self.assertEqual([t_split], t.splits)
    self.assertEqual(asset_bananas, t_split.asset)

  def test_category(self):
    self.assertEqual(None, account.TransactionCategory.parse(None))
    self.assertEqual(None, account.TransactionCategory.parse(""))

    for enum in account.TransactionCategory:
      self.assertEqual(enum, account.TransactionCategory.parse(enum))
      self.assertEqual(enum, account.TransactionCategory.parse(enum.name))
      self.assertEqual(enum, account.TransactionCategory.parse(enum.value))

    # enum_map = {}
    # for s, enum in enum_map.items():
    #   self.assertEqual(enum, account.TransactionCategory.parse(s.upper()))

    self.assertRaises(ValueError, account.TransactionCategory.parse, "FAKE")


class TestAccount(TestBase):
  """Test Account class
  """

  def test_init_properties(self):
    session = self._get_session()
    models.metadata_create_all(session)

    d = {
        "name": self.random_string(),
        "institution": self.random_string(),
        "category": account.AccountCategory.CASH
    }

    a = account.Account(**d)
    session.add(a)
    session.commit()

    self.assertEqual(d["name"], a.name)
    self.assertEqual(d["institution"], a.institution)
    self.assertEqual(d["category"], a.category)
    self.assertEqual([], a.transactions)
    self.assertIsNone(a.opened_on)
    self.assertIsNone(a.updated_on)

    # Test default and hidden properties
    d["id"] = a.id
    d["opened_on"] = None
    d["updated_on"] = None
    result = a.to_dict()
    self.assertDictEqual(d, result)

  def test_add_transactions(self):
    session = self._get_session()
    models.metadata_create_all(session)

    today = datetime.date.today()

    d = {
        "name": self.random_string(),
        "institution": self.random_string(),
        "category": account.AccountCategory.CASH
    }

    a = account.Account(**d)
    session.add(a)
    session.commit()

    self.assertEqual([], a.transactions)
    self.assertIsNone(a.opened_on)
    self.assertIsNone(a.updated_on)

    # Transaction are sorted by date

    t_today = account.Transaction(account=a,
                                  date=today,
                                  total=self._RNG.uniform(-1, 1),
                                  statement=self.random_string())
    session.add(t_today)
    session.commit()

    self.assertEqual([t_today], a.transactions)
    self.assertEqual(today, a.opened_on)
    self.assertEqual(today, a.updated_on)

    t_before = account.Transaction(account=a,
                                   date=today - datetime.timedelta(days=1),
                                   total=self._RNG.uniform(-1, 1),
                                   statement=self.random_string())
    session.add(t_before)
    session.commit()

    self.assertEqual([t_before, t_today], a.transactions)
    self.assertEqual(t_before.date, a.opened_on)
    self.assertEqual(today, a.updated_on)

    t_after = account.Transaction(account=a,
                                  date=today + datetime.timedelta(days=1),
                                  total=self._RNG.uniform(-1, 1),
                                  statement=self.random_string())
    session.add(t_after)
    session.commit()

    self.assertEqual([t_before, t_today, t_after], a.transactions)
    self.assertEqual(t_before.date, a.opened_on)
    self.assertEqual(t_after.date, a.updated_on)

  def test_category(self):
    self.assertEqual(None, account.AccountCategory.parse(None))
    self.assertEqual(None, account.AccountCategory.parse(""))

    for enum in account.AccountCategory:
      self.assertEqual(enum, account.AccountCategory.parse(enum))
      self.assertEqual(enum, account.AccountCategory.parse(enum.name))
      self.assertEqual(enum, account.AccountCategory.parse(enum.value))

    # enum_map = {}
    # for s, enum in enum_map.items():
    #   self.assertEqual(enum, account.AccountCategory.parse(s.upper()))

    self.assertRaises(ValueError, account.AccountCategory.parse, "FAKE")
