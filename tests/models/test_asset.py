"""Test module nummus.models.asset
"""

import datetime
from decimal import Decimal

from nummus import models
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           AssetSplit, AssetValuation, Transaction,
                           TransactionSplit)

from tests.base import TestBase


class TestAssetSplit(TestBase):
  """Test AssetSplit class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    a = Asset(name=self.random_string(), category=AssetCategory.CASH)
    s.add(a)
    s.commit()

    d = {
        "asset_id": a.id,
        "multiplier": self.random_decimal(1, 10),
        "date": datetime.date.today()
    }

    v = AssetSplit(**d)
    s.add(v)
    s.commit()

    self.assertEqual(d["asset_id"], v.asset_id)
    self.assertEqual(a, v.asset)
    self.assertEqual(d["multiplier"], v.multiplier)
    self.assertEqual(d["date"], v.date)

    # Test default and hidden properties
    d.pop("asset_id")
    result = v.to_dict()
    self.assertDictEqual(d, result)

    # Set via asset=a
    d = {
        "asset": a,
        "multiplier": self.random_decimal(1, 10),
        "date": datetime.date.today()
    }

    v = AssetSplit(**d)
    s.add(v)
    s.commit()

    self.assertEqual(a, v.asset)
    self.assertEqual(d["multiplier"], v.multiplier)
    self.assertEqual(d["date"], v.date)

    # Set an uncommitted Asset
    a = Asset(name=self.random_string(), category=AssetCategory.SECURITY)
    self.assertRaises(ValueError, setattr, v, "asset", a)

    # Set an not an Asset
    self.assertRaises(TypeError, setattr, v, "asset", self.random_string())


class TestAssetValuation(TestBase):
  """Test AssetValuation class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    a = Asset(name=self.random_string(), category=AssetCategory.CASH)
    s.add(a)
    s.commit()

    d = {
        "asset_id": a.id,
        "value": self.random_decimal(0, 1),
        "date": datetime.date.today()
    }

    v = AssetValuation(**d)
    s.add(v)
    s.commit()

    self.assertEqual(d["asset_id"], v.asset_id)
    self.assertEqual(a, v.asset)
    self.assertEqual(d["value"], v.value)
    self.assertEqual(d["date"], v.date)

    # Test default and hidden properties
    d.pop("asset_id")
    result = v.to_dict()
    self.assertDictEqual(d, result)

    # Set an uncommitted Asset
    a = Asset(name=self.random_string(), category=AssetCategory.SECURITY)
    self.assertRaises(ValueError, setattr, v, "asset", a)

    # Set an not an Asset
    self.assertRaises(TypeError, setattr, v, "asset", self.random_string())


class TestAsset(TestBase):
  """Test Asset class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string(),
        "img_suffix": self.random_string()
    }

    a = Asset(**d)
    s.add(a)
    s.commit()

    self.assertEqual(d["name"], a.name)
    self.assertEqual(d["description"], a.description)
    self.assertEqual(d["category"], a.category)
    self.assertEqual(d["unit"], a.unit)
    self.assertEqual(d["tag"], a.tag)
    self.assertEqual(d["img_suffix"], a.img_suffix)
    self.assertEqual(f"{a.uuid}{d['img_suffix']}", a.image_name)

    # Test default and hidden properties
    d["uuid"] = a.uuid
    d.pop("img_suffix")
    result = a.to_dict()
    self.assertDictEqual(d, result)

    a.img_suffix = None
    self.assertIsNone(a.image_name)

    d = {
        "asset_id": a.id,
        "value": self.random_decimal(0, 1),
        "date": datetime.date.today()
    }

    v = AssetValuation(**d)
    s.add(v)
    s.commit()

    s.delete(a)

    # Cannot delete Parent before all children
    self.assertRaises(models.exc.IntegrityError, s.commit)
    s.rollback()  # Undo the attempt

    s.delete(v)
    s.commit()
    s.delete(a)
    s.commit()

    result = s.query(Asset).all()
    self.assertEqual([], result)
    result = s.query(AssetValuation).all()
    self.assertEqual([], result)

  def test_add_valuations(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string(),
        "img_suffix": self.random_string()
    }

    a = Asset(**d)
    s.add(a)
    s.commit()

    v_today = AssetValuation(asset=a,
                             date=today,
                             value=self.random_decimal(-1, 1))
    s.add(v_today)
    s.commit()

  def test_get_value(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string(),
        "img_suffix": self.random_string()
    }

    a = Asset(**d)
    s.add(a)
    s.commit()

    v_today = AssetValuation(asset=a,
                             date=today,
                             value=self.random_decimal(-1, 1))
    v_before = AssetValuation(asset=a,
                              date=today - datetime.timedelta(days=2),
                              value=self.random_decimal(-1, 1))
    v_after = AssetValuation(asset=a,
                             date=today + datetime.timedelta(days=2),
                             value=self.random_decimal(-1, 1))
    s.add_all((v_today, v_before, v_after))
    s.commit()

    target_dates = [
        today + datetime.timedelta(days=i) for i in range(-3, 3 + 1)
    ]
    target_values = [
        0, v_before.value, v_before.value, v_today.value, v_today.value,
        v_after.value, v_after.value
    ]

    r_dates, r_values = a.get_value(target_dates[0], target_dates[-1])
    self.assertListEqual(target_dates, r_dates)
    self.assertListEqual(target_values, r_values)

    # Test single value
    r_dates, r_values = a.get_value(today, today)
    self.assertListEqual([today], r_dates)
    self.assertListEqual([v_today.value], r_values)

    # Test single value
    r_dates, r_values = a.get_value(tomorrow, tomorrow)
    self.assertListEqual([tomorrow], r_dates)
    self.assertListEqual([v_today.value], r_values)

    # Test single value
    long_ago = today - datetime.timedelta(days=7)
    r_dates, r_values = a.get_value(long_ago, long_ago)
    self.assertListEqual([long_ago], r_dates)
    self.assertListEqual([Decimal(0)], r_values)

  def test_update_splits(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    multiplier_0 = round(self.random_decimal(1, 10))
    multiplier_1 = round(self.random_decimal(1, 10))
    multiplier = multiplier_0 * multiplier_1
    value_today = self.random_decimal(1, 10)
    value_yesterday = value_today * multiplier

    # Create assets and accounts
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH)
    s.add_all((a, acct))
    s.commit()

    v = AssetValuation(asset=a,
                       date=today - datetime.timedelta(days=100),
                       value=value_today)
    s.add(v)
    s.commit()

    # Multiple splits that need be included on the first valuation
    split_0 = AssetSplit(asset=a, date=today, multiplier=multiplier_0)
    split_1 = AssetSplit(asset=a, date=today, multiplier=multiplier_1)
    s.add_all((split_0, split_1))
    s.commit()

    # Splits are done after hours
    # A split on today means trading occurs at yesterday / multiplier pricing
    txn_0 = Transaction(account=acct,
                        date=yesterday,
                        total=value_yesterday,
                        statement=self.random_string())
    t_split_0 = TransactionSplit(total=txn_0.total,
                                 parent=txn_0,
                                 asset=a,
                                 asset_quantity_unadjusted=1)
    s.add_all((txn_0, t_split_0))

    txn_1 = Transaction(account=acct,
                        date=today,
                        total=value_today,
                        statement=self.random_string())
    t_split_1 = TransactionSplit(total=txn_1.total,
                                 parent=txn_1,
                                 asset=a,
                                 asset_quantity_unadjusted=1)
    s.add_all((txn_1, t_split_1))

    s.commit()

    # Do split updates
    a.update_splits()
    s.commit()

    self.assertEqual(1, t_split_0.asset_quantity_unadjusted)
    self.assertEqual(1, t_split_1.asset_quantity_unadjusted)

    self.assertEqual(1 * multiplier, t_split_0.asset_quantity)
    self.assertEqual(1, t_split_1.asset_quantity)

    _, r_assets = acct.get_asset_qty(yesterday, today)
    r_values = r_assets[a.uuid]
    target_values = [multiplier, multiplier + 1]
    self.assertEqual(target_values, r_values)

    _, _, r_assets = acct.get_value(yesterday, today)
    r_values = r_assets[a.uuid]
    target_values = [value_yesterday, value_yesterday + value_today]
    self.assertEqual(target_values, r_values)
