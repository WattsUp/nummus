"""Test module nummus.models.asset
"""

import datetime

from nummus import models
from nummus.models import asset

from tests.base import TestBase


class TestAssetValuation(TestBase):
  """Test AssetValuation class
  """

  def test_init_properties(self):
    session = self._get_session()
    models.metadata_create_all(session)

    a = asset.Asset(name=self.random_string(),
                    category=asset.AssetCategory.CASH)
    session.add(a)
    session.commit()

    d = {
        "asset_id": a.id,
        "value": self._RNG.uniform(0, 1),
        "date": datetime.date.today()
    }

    v = asset.AssetValuation(**d)
    session.add(v)
    session.commit()

    self.assertEqual(d["asset_id"], v.asset_id)
    self.assertEqual(a, v.asset)
    self.assertEqual(a.uuid, v.asset_uuid)
    self.assertEqual(d["value"], v.value)
    self.assertEqual(1.0, v.multiplier)
    self.assertEqual(d["date"], v.date)

    d["multiplier"] = self._RNG.uniform(0, 1)
    v.update(d)
    self.assertEqual(d["multiplier"], v.multiplier)

    # Test default and hidden properties
    d.pop("asset_id")
    d["asset_uuid"] = a.uuid
    result = v.to_dict()
    self.assertDictEqual(d, result)


class TestAsset(TestBase):
  """Test Asset class
  """

  def test_init_properties(self):
    session = self._get_session()
    models.metadata_create_all(session)

    d = {
        "name": self.random_string(),
        "description": self.random_string(),
        "category": asset.AssetCategory.SECURITY,
        "unit": self.random_string(),
        "tag": self.random_string()
    }

    a = asset.Asset(**d)
    session.add(a)
    session.commit()

    self.assertEqual(d["name"], a.name)
    self.assertEqual(d["description"], a.description)
    self.assertEqual(d["category"], a.category)
    self.assertEqual(d["unit"], a.unit)
    self.assertEqual(d["tag"], a.tag)
    self.assertEqual([], a.valuations)

    # Test default and hidden properties
    d["uuid"] = a.uuid
    result = a.to_dict()
    self.assertDictEqual(d, result)

    d = {
        "asset_id": a.id,
        "value": self._RNG.uniform(0, 1),
        "multiplier": self._RNG.uniform(0, 1),
        "date": datetime.date.today()
    }

    v = asset.AssetValuation(**d)
    session.add(v)
    session.commit()

    self.assertEqual([v], a.valuations)

    session.delete(a)

    # Cannot delete Parent before all children
    self.assertRaises(models.exc.IntegrityError, session.commit)
    session.rollback()  # Undo the attempt

    session.delete(a)
    session.delete(v)
    session.commit()

    result = session.query(asset.Asset).all()
    self.assertEqual([], result)
    result = session.query(asset.AssetValuation).all()
    self.assertEqual([], result)

  def test_category(self):
    self.assertEqual(None, asset.AssetCategory.parse(None))
    self.assertEqual(None, asset.AssetCategory.parse(""))

    for enum in asset.AssetCategory:
      self.assertEqual(enum, asset.AssetCategory.parse(enum))
      self.assertEqual(enum, asset.AssetCategory.parse(enum.name))
      self.assertEqual(enum, asset.AssetCategory.parse(enum.value))

    # enum_map = {}
    # for s, enum in enum_map.items():
    #   self.assertEqual(enum, asset.AssetCategory.parse(s.upper()))

    self.assertRaises(ValueError, asset.AssetCategory.parse, "FAKE")
