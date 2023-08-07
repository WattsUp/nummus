"""Test module nummus.models.asset
"""

import datetime

from nummus import models
from nummus.models import asset

from tests.base import TestBase


class TestAssetSplit(TestBase):
  """Test AssetSplit class
  """

  def test_init_properties(self):
    session = self.get_session()
    models.metadata_create_all(session)

    a = asset.Asset(name=self.random_string(),
                    category=asset.AssetCategory.CASH)
    session.add(a)
    session.commit()

    d = {
        "asset_id": a.id,
        "multiplier": self.random_decimal(1, 10),
        "date": datetime.date.today()
    }

    v = asset.AssetSplit(**d)
    session.add(v)
    session.commit()

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

    v = asset.AssetSplit(**d)
    session.add(v)
    session.commit()

    self.assertEqual(a, v.asset)
    self.assertEqual(d["multiplier"], v.multiplier)
    self.assertEqual(d["date"], v.date)

    # Set an uncommitted Asset
    a = asset.Asset(name=self.random_string(),
                    category=asset.AssetCategory.SECURITY)
    self.assertRaises(ValueError, setattr, v, "asset", a)

    # Set an not an Asset
    self.assertRaises(TypeError, setattr, v, "asset", self.random_string())


class TestAssetValuation(TestBase):
  """Test AssetValuation class
  """

  def test_init_properties(self):
    session = self.get_session()
    models.metadata_create_all(session)

    a = asset.Asset(name=self.random_string(),
                    category=asset.AssetCategory.CASH)
    session.add(a)
    session.commit()

    d = {
        "asset_id": a.id,
        "value": self.random_decimal(0, 1),
        "date": datetime.date.today()
    }

    v = asset.AssetValuation(**d)
    session.add(v)
    session.commit()

    self.assertEqual(d["asset_id"], v.asset_id)
    self.assertEqual(a, v.asset)
    self.assertEqual(d["value"], v.value)
    self.assertEqual(d["date"], v.date)

    # Test default and hidden properties
    d.pop("asset_id")
    result = v.to_dict()
    self.assertDictEqual(d, result)

    # Set an uncommitted Asset
    a = asset.Asset(name=self.random_string(),
                    category=asset.AssetCategory.SECURITY)
    self.assertRaises(ValueError, setattr, v, "asset", a)

    # Set an not an Asset
    self.assertRaises(TypeError, setattr, v, "asset", self.random_string())


class TestAsset(TestBase):
  """Test Asset class
  """

  def test_init_properties(self):
    session = self.get_session()
    models.metadata_create_all(session)

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": asset.AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string(),
        "img_suffix": self.random_string()
    }

    a = asset.Asset(**d)
    session.add(a)
    session.commit()

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

    v = asset.AssetValuation(**d)
    session.add(v)
    session.commit()

    session.delete(a)

    # Cannot delete Parent before all children
    self.assertRaises(models.exc.IntegrityError, session.commit)
    session.rollback()  # Undo the attempt

    session.delete(v)
    session.commit()
    session.delete(a)
    session.commit()

    result = session.query(asset.Asset).all()
    self.assertEqual([], result)
    result = session.query(asset.AssetValuation).all()
    self.assertEqual([], result)

  def test_add_valuations(self):
    session = self.get_session()
    models.metadata_create_all(session)

    today = datetime.date.today()

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": asset.AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string(),
        "img_suffix": self.random_string()
    }

    a = asset.Asset(**d)
    session.add(a)
    session.commit()

    v_today = asset.AssetValuation(asset=a,
                                   date=today,
                                   value=self.random_decimal(-1, 1))
    session.add(v_today)
    session.commit()

  def test_get_value(self):
    session = self.get_session()
    models.metadata_create_all(session)

    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": asset.AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string(),
        "img_suffix": self.random_string()
    }

    a = asset.Asset(**d)
    session.add(a)
    session.commit()

    v_today = asset.AssetValuation(asset=a,
                                   date=today,
                                   value=self.random_decimal(-1, 1))
    v_before = asset.AssetValuation(asset=a,
                                    date=today - datetime.timedelta(days=2),
                                    value=self.random_decimal(-1, 1))
    v_after = asset.AssetValuation(asset=a,
                                   date=today + datetime.timedelta(days=2),
                                   value=self.random_decimal(-1, 1))
    session.add_all((v_today, v_before, v_after))
    session.commit()

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
