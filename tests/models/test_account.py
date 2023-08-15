"""Test module nummus.models.account
"""

import datetime

from nummus import models
from nummus.models import (Account, AccountCategory, Asset, AssetList,
                           AssetCategory, AssetValuation, Transaction,
                           TransactionCategory, TransactionSplit)

from tests.base import TestBase


class TestTransaction(TestBase):
  """Test Transaction class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH)
    s.add(acct)
    s.commit()

    asset = Asset(name="bananas", category=AssetCategory.ITEM)
    s.add(asset)
    s.commit()

    d = {
        "account": acct,
        "date": datetime.date.today(),
        "total": self.random_decimal(-1, 1),
        "statement": self.random_string()
    }

    txn = Transaction(**d)
    s.add(txn)
    s.commit()

    self.assertEqual(acct, txn.account)
    self.assertEqual(acct.id, txn.account_id)
    self.assertEqual(acct.uuid, txn.account_uuid)
    self.assertEqual(d["date"], txn.date)
    self.assertEqual(d["total"], txn.total)
    self.assertEqual(d["statement"], txn.statement)
    self.assertFalse(txn.locked, "Transaction is unexpectedly locked")

    d.pop("account")
    d["uuid"] = txn.uuid
    d["account_uuid"] = acct.uuid
    d["splits"] = []
    d["locked"] = False
    result = txn.to_dict()
    self.assertDictEqual(d, result)

    d = {"total": self.random_decimal(-1, 1), "parent": txn}

    t_split_0 = TransactionSplit(**d)
    s.add(t_split_0)
    s.commit()
    self.assertEqual(t_split_0.parent, txn)
    self.assertEqual(t_split_0.parent_id, txn.id)
    self.assertIsNone(t_split_0.asset)
    self.assertIsNone(t_split_0.asset_id)
    self.assertIsNone(t_split_0.asset_uuid)
    self.assertIsNone(t_split_0.asset_quantity)
    self.assertIsNone(t_split_0.asset_quantity_unadjusted)

    result = t_split_0.to_dict()
    self.assertEqual(t_split_0.uuid, result.pop("uuid"))
    self.assertEqual(t_split_0.total, result.pop("total"))
    self.assertEqual(acct.uuid, result.pop("account_uuid"))
    self.assertEqual(txn.date, result.pop("date"))
    self.assertFalse(result.pop("locked"))
    self.assertEqual(txn.uuid, result.pop("parent_uuid"))
    # Rest should be None
    for k, v in result.items():
      self.assertIsNone(v, f"result[{k}] is not None")

    d = {
        "total": self.random_decimal(-1, 0),
        "sales_tax": self.random_decimal(-1, 0),
        "payee": self.random_string(),
        "description": self.random_string(),
        "category": TransactionCategory.FOOD,
        "subcategory": self.random_string(),
        "tag": self.random_string(),
        "asset": asset,
        "asset_quantity_unadjusted": self.random_decimal(-1, 1, precision=18),
        "parent": txn
    }

    t_split_1 = TransactionSplit(**d)
    s.add(t_split_1)
    s.commit()

    # Test default and hidden properties
    d.pop("asset")
    d.pop("parent")
    d["uuid"] = t_split_1.uuid
    d["account_uuid"] = acct.uuid
    d["date"] = txn.date
    d["asset_uuid"] = asset.uuid
    d["parent_uuid"] = txn.uuid
    d["asset_quantity"] = d.pop("asset_quantity_unadjusted")
    d["locked"] = False
    result = t_split_1.to_dict()
    self.assertDictEqual(d, result)

    self.assertEqual([t_split_0, t_split_1], txn.splits)
    self.assertEqual(asset, t_split_1.asset)
    self.assertEqual(d["asset_quantity"], t_split_1.asset_quantity_unadjusted)

    # Remove asset
    t_split_1.asset = None
    s.commit()
    self.assertIsNone(t_split_1.asset)
    self.assertIsNone(t_split_1.asset_id)
    self.assertIsNone(t_split_1.asset_uuid)

    # Set an uncommitted Asset
    asset = Asset(name=self.random_string(), category=AssetCategory.SECURITY)
    self.assertRaises(ValueError, setattr, t_split_1, "asset", asset)

    # Set an not an Asset
    self.assertRaises(TypeError, setattr, t_split_1, "asset",
                      self.random_string())

    # Set an uncommitted Account
    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH)
    self.assertRaises(ValueError, setattr, txn, "account", acct)

    # Set an not an Account
    self.assertRaises(TypeError, setattr, txn, "account", self.random_string())

    # Set an not an Transaction
    self.assertRaises(TypeError, setattr, t_split_0, "parent",
                      self.random_string())

    # Set parent_id directly
    self.assertRaises(PermissionError, setattr, t_split_0, "parent_id", txn.id)

    # Set asset_id directly
    self.assertRaises(PermissionError, setattr, t_split_0, "asset_id", asset.id)

    # Set account_id directly
    self.assertRaises(PermissionError, setattr, txn, "account_id", acct.id)

  def test_is_valid_amount(self):
    not_covered = list(TransactionCategory)

    cat_inflow = [TransactionCategory.INCOME]
    cat_outflow = [
        TransactionCategory.HOME, TransactionCategory.FOOD,
        TransactionCategory.SHOPPING, TransactionCategory.HOBBIES,
        TransactionCategory.SERVICES, TransactionCategory.TRAVEL
    ]
    cat_either = [TransactionCategory.INSTRUMENT, TransactionCategory.TRANSFER]

    for cat in cat_inflow:
      self.assertTrue(cat.is_valid_amount(10),
                      f"Positive amount is invalid for {cat}")
      self.assertTrue(cat.is_valid_amount(0), f"Zero is invalid for {cat}")
      self.assertFalse(cat.is_valid_amount(-10),
                       f"Negative amount is valid for {cat}")
      not_covered.remove(cat)

    for cat in cat_outflow:
      self.assertFalse(cat.is_valid_amount(10),
                       f"Positive amount is invalid for {cat}")
      self.assertTrue(cat.is_valid_amount(0), f"Zero is invalid for {cat}")
      self.assertTrue(cat.is_valid_amount(-10),
                      f"Negative amount is invalid for {cat}")
      not_covered.remove(cat)

    for cat in cat_either:
      self.assertTrue(cat.is_valid_amount(10),
                      f"Positive amount is invalid for {cat}")
      self.assertTrue(cat.is_valid_amount(0), f"Zero is invalid for {cat}")
      self.assertTrue(cat.is_valid_amount(-10),
                      f"Negative amount is invalid for {cat}")
      not_covered.remove(cat)

    self.assertEqual(0, len(not_covered),
                     f"Categories not covered: {not_covered}")

  def test_validate_category(self):
    s = self.get_session()
    models.metadata_create_all(s)

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH)
    s.add(acct)
    s.commit()

    today = datetime.date.today()

    # No category is okay
    txn = Transaction(account=acct,
                      date=today,
                      statement=self.random_string(),
                      total=10)
    t_split = TransactionSplit(parent=txn, total=10, category=None)
    s.add_all((txn, t_split))
    s.commit()

    # Positive total is okay for INCOME
    t_split.category = TransactionCategory.INCOME

    # Positive total is not okay for FOOD
    self.assertRaises(ValueError, setattr, t_split, "category",
                      TransactionCategory.FOOD)

    # No category is okay
    txn = Transaction(account=acct,
                      date=today,
                      statement=self.random_string(),
                      total=-10)
    t_split = TransactionSplit(parent=txn, total=-10, category=None)
    s.add_all((txn, t_split))
    s.commit()

    # Negative total is okay for HOME
    t_split.category = TransactionCategory.HOME

    # Negative total is not okay for INCOME
    self.assertRaises(ValueError, setattr, t_split, "category",
                      TransactionCategory.INCOME)

  def test_asset_quantity(self):
    s = self.get_session()
    models.metadata_create_all(s)

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.CASH)
    s.add(acct)
    s.commit()

    today = datetime.date.today()

    qty = self.random_decimal(10, 100, precision=18)
    txn = Transaction(account=acct,
                      date=today,
                      statement=self.random_string(),
                      total=10)
    t_split = TransactionSplit(parent=txn,
                               total=10,
                               asset_quantity_unadjusted=qty)
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


class TestAccount(TestBase):
  """Test Account class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    d = {
        "name": self.random_string(),
        "institution": self.random_string(),
        "category": AccountCategory.CASH
    }

    acct = Account(**d)
    s.add(acct)
    s.commit()

    self.assertEqual(d["name"], acct.name)
    self.assertEqual(d["institution"], acct.institution)
    self.assertEqual(d["category"], acct.category)
    self.assertIsNone(acct.opened_on)
    self.assertIsNone(acct.updated_on)

    # Test default and hidden properties
    d["uuid"] = acct.uuid
    d["opened_on"] = None
    d["updated_on"] = None
    result = acct.to_dict()
    self.assertDictEqual(d, result)

  def test_add_transactions(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()

    d = {
        "name": self.random_string(),
        "institution": self.random_string(),
        "category": AccountCategory.CASH
    }

    acct = Account(**d)
    s.add(acct)
    s.commit()

    self.assertIsNone(acct.opened_on)
    self.assertIsNone(acct.updated_on)

    # Transaction are sorted by date

    t_today = Transaction(account=acct,
                          date=today,
                          total=self.random_decimal(-1, 1),
                          statement=self.random_string())
    s.add(t_today)
    s.commit()

    self.assertEqual(today, acct.opened_on)
    self.assertEqual(today, acct.updated_on)

    t_before = Transaction(account=acct,
                           date=today - datetime.timedelta(days=1),
                           total=self.random_decimal(-1, 1),
                           statement=self.random_string())
    s.add(t_before)
    s.commit()

    self.assertEqual(t_before.date, acct.opened_on)
    self.assertEqual(today, acct.updated_on)

    t_after = Transaction(account=acct,
                          date=today + datetime.timedelta(days=1),
                          total=self.random_decimal(-1, 1),
                          statement=self.random_string())
    s.add(t_after)
    s.commit()

    self.assertEqual(t_before.date, acct.opened_on)
    self.assertEqual(t_after.date, acct.updated_on)

  def test_get_asset_qty(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.INVESTMENT)
    assets: AssetList = []
    for _ in range(3):
      new_asset = Asset(name=self.random_string(),
                        category=AssetCategory.SECURITY)
      assets.append(new_asset)
    s.add(acct)
    s.add_all(assets)
    s.commit()

    target_dates = [
        (today + datetime.timedelta(days=i)) for i in range(-3, 3 + 1)
    ]
    target_qty = {}

    result_dates, result_qty = acct.get_asset_qty(target_dates[0],
                                                  target_dates[-1])
    self.assertEqual(target_dates, result_dates)
    self.assertEqual(target_qty, result_qty)

    # Fund account on first day
    txn = Transaction(account=acct,
                      date=target_dates[1],
                      total=self.random_decimal(10, 100),
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn, total=txn.total)
    s.add_all((txn, t_split))
    s.commit()

    # Buy asset[0] on the second day
    q0 = self.random_decimal(0, 10)
    txn = Transaction(account=acct,
                      date=target_dates[1],
                      total=self.random_decimal(-10, -1),
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn,
                               total=txn.total,
                               asset=assets[0],
                               asset_quantity_unadjusted=q0)
    s.add_all((txn, t_split))
    s.commit()

    target_qty = {assets[0].uuid: [0, q0, q0, q0, q0, q0, q0]}

    result_dates, result_qty = acct.get_asset_qty(target_dates[0],
                                                  target_dates[-1])
    self.assertEqual(target_dates, result_dates)
    self.assertEqual(target_qty, result_qty)

    # Sell asset[0] on the last day
    q1 = self.random_decimal(0, 10)
    txn = Transaction(account=acct,
                      date=target_dates[-1],
                      total=self.random_decimal(1, 10),
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn,
                               total=txn.total,
                               asset=assets[0],
                               asset_quantity_unadjusted=-q1)
    s.add_all((txn, t_split))
    s.commit()

    target_qty = {assets[0].uuid: [0, q0, q0, q0, q0, q0, q0 - q1]}

    result_dates, result_qty = acct.get_asset_qty(target_dates[0],
                                                  target_dates[-1])
    self.assertEqual(target_dates, result_dates)
    self.assertEqual(target_qty, result_qty)

    # Buy asset[1] on today
    q2 = self.random_decimal(0, 10)
    txn = Transaction(account=acct,
                      date=today,
                      total=self.random_decimal(-10, -1),
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn,
                               total=txn.total,
                               asset=assets[1],
                               asset_quantity_unadjusted=q2)
    s.add_all((txn, t_split))
    s.commit()

    target_qty = {
        assets[0].uuid: [0, q0, q0, q0],
        assets[1].uuid: [0, 0, 0, q2]
    }

    result_dates, result_qty = acct.get_asset_qty(target_dates[0], today)
    self.assertEqual(target_dates[0:4], result_dates)
    self.assertEqual(target_qty, result_qty)

    # Test single value
    target_qty = {assets[0].uuid: [q0], assets[1].uuid: [q2]}
    result_dates, result_qty = acct.get_asset_qty(today, today)
    self.assertListEqual([today], result_dates)
    self.assertEqual(target_qty, result_qty)

    # Test single value
    future = target_dates[-1] + datetime.timedelta(days=1)
    target_qty = {assets[0].uuid: [q0 - q1], assets[1].uuid: [q2]}
    result_dates, result_qty = acct.get_asset_qty(future, future)
    self.assertListEqual([future], result_dates)
    self.assertEqual(target_qty, result_qty)

  def test_get_value(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.INVESTMENT)
    assets: AssetList = []
    for _ in range(3):
      new_asset = Asset(name=self.random_string(),
                        category=AssetCategory.SECURITY)
      assets.append(new_asset)
    s.add(acct)
    s.add_all(assets)
    s.commit()

    target_dates = [
        (today + datetime.timedelta(days=i)) for i in range(-3, 3 + 1)
    ]
    target_values = [0] * 7
    target_assets = {}
    start = target_dates[0]
    end = target_dates[-1]

    r_dates, r_values, r_assets = acct.get_value(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_values, r_values)
    self.assertEqual(target_assets, r_assets)

    # Fund account on first day
    t_fund = self.random_decimal(10, 100)
    txn = Transaction(account=acct,
                      date=target_dates[1],
                      total=t_fund,
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn, total=txn.total)
    s.add_all((txn, t_split))
    s.commit()

    target_values = [0, t_fund, t_fund, t_fund, t_fund, t_fund, t_fund]

    r_dates, r_values, r_assets = acct.get_value(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_values, r_values)
    self.assertEqual(target_assets, r_assets)

    # Buy asset[0] on the second day
    t0 = self.random_decimal(-10, -1)
    q0 = self.random_decimal(0, 10)
    txn = Transaction(account=acct,
                      date=target_dates[1],
                      total=t0,
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn,
                               total=txn.total,
                               asset=assets[0],
                               asset_quantity_unadjusted=q0)
    s.add_all((txn, t_split))
    s.commit()

    target_values = [
        0, t_fund + t0, t_fund + t0, t_fund + t0, t_fund + t0, t_fund + t0,
        t_fund + t0
    ]
    target_assets = {assets[0].uuid: [0] * 7}

    r_dates, r_values, r_assets = acct.get_value(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_values, r_values)
    self.assertEqual(target_assets, r_assets)

    # Sell asset[0] on the last day
    t1 = self.random_decimal(1, 10)
    q1 = self.random_decimal(0, 10)
    txn = Transaction(account=acct,
                      date=target_dates[-1],
                      total=t1,
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn,
                               total=txn.total,
                               asset=assets[0],
                               asset_quantity_unadjusted=-q1)
    s.add_all((txn, t_split))
    s.commit()

    target_values = [
        0, t_fund + t0, t_fund + t0, t_fund + t0, t_fund + t0, t_fund + t0,
        t_fund + t0 + t1
    ]
    target_assets = {assets[0].uuid: [0] * 7}

    r_dates, r_values, r_assets = acct.get_value(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_values, r_values)
    self.assertEqual(target_assets, r_assets)

    # Add valuations to Asset
    prices = self.random_decimal(1, 10, size=len(target_dates))
    for date, p in zip(target_dates, prices):
      v = AssetValuation(asset=assets[0], date=date, value=p)
      s.add(v)
    s.commit()

    asset_values = [
        round(p * q, 6)
        for p, q in zip(prices, [0, q0, q0, q0, q0, q0, q0 - q1])
    ]
    target_values = [c + v for c, v in zip(target_values, asset_values)]
    target_assets = {assets[0].uuid: asset_values}

    r_dates, r_values, r_assets = acct.get_value(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_values, r_values)
    self.assertEqual(target_assets, r_assets)

    # Test single value
    r_dates, r_values, r_assets = acct.get_value(today, today)
    self.assertEqual([today], r_dates)
    self.assertEqual([target_values[3]], r_values)
    self.assertEqual({assets[0].uuid: [asset_values[3]]}, r_assets)

    # Test single value
    future = target_dates[-1] + datetime.timedelta(days=1)
    r_dates, r_values, r_assets = acct.get_value(future, future)
    self.assertEqual([future], r_dates)
    self.assertEqual([target_values[-1]], r_values)
    self.assertEqual({assets[0].uuid: [asset_values[-1]]}, r_assets)

  def test_get_cash_flow(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()

    acct = Account(name=self.random_string(),
                   institution=self.random_string(),
                   category=AccountCategory.INVESTMENT)
    s.add(acct)
    s.commit()

    target_dates = [
        (today + datetime.timedelta(days=i)) for i in range(-3, 3 + 1)
    ]
    target_categories = {cat: [0] * 7 for cat in TransactionCategory}
    target_categories["unknown-inflow"] = [0] * 7
    target_categories["unknown-outflow"] = [0] * 7
    start = target_dates[0]
    end = target_dates[-1]

    r_dates, r_categories = acct.get_cash_flow(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_categories, r_categories)

    # Fund account on second day
    t_fund = self.random_decimal(10, 100)
    txn = Transaction(account=acct,
                      date=target_dates[1],
                      total=t_fund,
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn, total=txn.total)
    s.add_all((txn, t_split))
    s.commit()

    target_categories["unknown-inflow"][1] += t_fund

    r_dates, r_categories = acct.get_cash_flow(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_categories, r_categories)

    # Buy something on the second day
    t0 = self.random_decimal(-10, -1)
    txn = Transaction(account=acct,
                      date=target_dates[1],
                      total=t0,
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn, total=txn.total)
    s.add_all((txn, t_split))
    s.commit()

    target_categories["unknown-outflow"][1] += t0

    r_dates, r_categories = acct.get_cash_flow(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_categories, r_categories)

    # Sell something on the last day
    t1 = self.random_decimal(1, 10)
    txn = Transaction(account=acct,
                      date=target_dates[-1],
                      total=t1,
                      statement=self.random_string())
    t_split = TransactionSplit(parent=txn,
                               total=txn.total,
                               category=TransactionCategory.INCOME)
    s.add_all((txn, t_split))
    s.commit()

    target_categories[TransactionCategory.INCOME][-1] += t1

    r_dates, r_categories = acct.get_cash_flow(start, end)
    self.assertEqual(target_dates, r_dates)
    self.assertEqual(target_categories, r_categories)

    # Test single value
    r_dates, r_categories = acct.get_cash_flow(today, today)
    self.assertEqual([today], r_dates)
    self.assertEqual({
        cat: [v[3]] for cat, v in target_categories.items()
    }, r_categories)

    r_dates, r_categories = acct.get_cash_flow(end, end)
    self.assertEqual([end], r_dates)
    self.assertEqual({
        cat: [v[-1]] for cat, v in target_categories.items()
    }, r_categories)
