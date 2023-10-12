"""Test module nummus.models.transaction
"""

import datetime

from nummus import models
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           Transaction, TransactionCategory, TransactionSplit)

from tests.base import TestBase


class TestTransaction(TestBase):
  """Test Transaction class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH,
                   closed=False)
    s.add(acct)
    s.commit()

    d = {
        "account_id": acct.id,
        "date": datetime.date.today(),
        "amount": self.random_decimal(-1, 1),
        "statement": self.random_string()
    }

    txn = Transaction(**d)
    s.add(txn)
    s.commit()

    self.assertEqual(acct.id, txn.account_id)
    self.assertEqual(d["date"], txn.date)
    self.assertEqual(d["amount"], txn.amount)
    self.assertEqual(d["statement"], txn.statement)
    self.assertFalse(txn.locked, "Transaction is unexpectedly locked")


class TestTransactionSplit(TestBase):
  """Test TransactionSplit class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH,
                   closed=False)
    s.add(acct)
    s.commit()

    asset = Asset(name="bananas", category=AssetCategory.ITEM)
    s.add(asset)
    s.commit()

    categories = TransactionCategory.add_default(s)
    t_cat = categories["Uncategorized"]

    d = {
        "account_id": acct.id,
        "date": datetime.date.today(),
        "amount": self.random_decimal(-1, 1),
        "statement": self.random_string()
    }

    txn = Transaction(**d)
    s.add(txn)
    s.commit()

    d = {
        "amount": self.random_decimal(-1, 1),
        "parent": txn,
        "category_id": t_cat.id
    }

    t_split_0 = TransactionSplit(**d)
    s.add(t_split_0)
    s.commit()
    self.assertEqual(t_split_0.parent, txn)
    self.assertEqual(t_split_0.parent_id, txn.id)
    self.assertEqual(t_split_0.category_id, t_cat.id)
    self.assertIsNone(t_split_0.asset_id)
    self.assertIsNone(t_split_0.asset_quantity)
    self.assertIsNone(t_split_0.asset_quantity_unadjusted)
    self.assertEqual(t_split_0.amount, d["amount"])
    self.assertEqual(t_split_0.date, txn.date)
    self.assertEqual(t_split_0.locked, txn.locked)
    self.assertEqual(t_split_0.account_id, acct.id)

    d = {
        "amount": self.random_decimal(-1, 0),
        "payee": self.random_string(),
        "description": self.random_string(),
        "category_id": t_cat.id,
        "tag": self.random_string(),
        "asset_id": asset.id,
        "asset_quantity_unadjusted": self.random_decimal(-1, 1, precision=18),
        "parent": txn
    }

    t_split_1 = TransactionSplit(**d)
    s.add(t_split_1)
    s.commit()
    self.assertEqual(t_split_1.parent, txn)
    self.assertEqual(t_split_1.parent_id, txn.id)
    self.assertEqual(t_split_1.category_id, t_cat.id)
    self.assertEqual(t_split_1.asset_id, asset.id)
    self.assertEqual(t_split_1.asset_quantity, d["asset_quantity_unadjusted"])
    self.assertEqual(t_split_1.asset_quantity_unadjusted,
                     d["asset_quantity_unadjusted"])
    self.assertEqual(t_split_1.amount, d["amount"])
    self.assertEqual(t_split_1.payee, d["payee"])
    self.assertEqual(t_split_1.description, d["description"])
    self.assertEqual(t_split_1.tag, d["tag"])
    self.assertEqual(t_split_1.date, txn.date)
    self.assertEqual(t_split_1.locked, txn.locked)
    self.assertEqual(t_split_1.account_id, acct.id)

    # Zero amounts are bad
    self.assertRaises(ValueError, setattr, t_split_0, "amount", 0)

    # Short strings are bad
    self.assertRaises(ValueError, setattr, t_split_0, "payee", "ab")

    # Set an not an Transaction
    self.assertRaises(TypeError, setattr, t_split_0, "parent",
                      self.random_string())

    # Set parent_id directly
    self.assertRaises(PermissionError, setattr, t_split_0, "parent_id", txn.id)

  def test_asset_quantity(self):
    s = self.get_session()
    models.metadata_create_all(s)

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH,
                   closed=False)
    s.add(acct)
    s.commit()

    categories = TransactionCategory.add_default(s)
    t_cat = categories["Uncategorized"]

    today = datetime.date.today()

    qty = self.random_decimal(10, 100, precision=18)
    txn = Transaction(account_id=acct.id,
                      date=today,
                      statement=self.random_string(),
                      amount=10)
    t_split = TransactionSplit(parent=txn,
                               amount=10,
                               asset_quantity_unadjusted=qty,
                               category_id=t_cat.id)
    s.add_all((txn, t_split))
    s.commit()

    self.assertEqual(qty, t_split.asset_quantity_unadjusted)
    self.assertEqual(qty, t_split.asset_quantity)

    multiplier = self.random_decimal(1, 10)
    t_split.adjust_asset_quantity(multiplier)
    self.assertEqual(qty, t_split.asset_quantity_unadjusted)
    self.assertEqual(qty * multiplier, t_split.asset_quantity)

    t_split.asset_quantity_unadjusted = None
    s.commit()

    self.assertIsNone(t_split.asset_quantity)

    self.assertRaises(ValueError, t_split.adjust_asset_quantity, multiplier)
