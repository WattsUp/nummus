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
    session = self.get_session()
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
    self.assertFalse(t.locked, "Transaction is unexpectedly locked")

    d.pop("account_id")
    d["uuid"] = t.uuid
    d["account_uuid"] = a.uuid
    d["splits"] = []
    d["locked"] = False
    result = t.to_dict()
    self.assertDictEqual(d, result)

    d = {"total": self._RNG.uniform(-1, 1), "parent_id": t.id}

    t_split_0 = account.TransactionSplit(**d)
    session.add(t_split_0)
    session.commit()

    result = t_split_0.to_dict()
    self.assertEqual(t_split_0.uuid, result.pop("uuid"))
    self.assertEqual(t_split_0.total, result.pop("total"))
    self.assertEqual(t.uuid, result.pop("parent_uuid"))
    # Rest should be None
    for k, v in result.items():
      self.assertIsNone(v, f"result[{k}] is not None")

    d = {
        "total": self._RNG.uniform(-1, 1),
        "sales_tax": self._RNG.uniform(-1, 0),
        "payee": self.random_string(),
        "description": self.random_string(),
        "category": account.TransactionCategory.FOOD,
        "subcategory": self.random_string(),
        "tag": self.random_string(),
        "asset_id": asset_bananas.id,
        "asset_quantity": self._RNG.uniform(-1, 1),
        "parent_id": t.id
    }

    t_split_1 = account.TransactionSplit(**d)
    session.add(t_split_1)
    session.commit()

    # Test default and hidden properties
    d.pop("asset_id")
    d.pop("parent_id")
    d["uuid"] = t_split_1.uuid
    d["asset_uuid"] = asset_bananas.uuid
    d["parent_uuid"] = t.uuid
    result = t_split_1.to_dict()
    self.assertDictEqual(d, result)

    self.assertEqual([t_split_0, t_split_1], t.splits)
    self.assertEqual(asset_bananas, t_split_1.asset)


class TestAccount(TestBase):
  """Test Account class
  """

  def test_init_properties(self):
    session = self.get_session()
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
    d["uuid"] = a.uuid
    d["opened_on"] = None
    d["updated_on"] = None
    result = a.to_dict()
    self.assertDictEqual(d, result)

  def test_add_transactions(self):
    session = self.get_session()
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
