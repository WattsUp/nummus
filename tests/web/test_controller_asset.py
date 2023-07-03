"""Test module nummus.web.controller_asset
"""

import datetime
import json
from nummus.models import (Asset, AssetCategory, AssetValuation,
                           NummusJSONEncoder)

from tests.web.base import WebTestBase


class TestControllerAsset(WebTestBase):
  """Test controller_asset methods
  """

  def test_create(self):
    p = self._portfolio

    name = self.random_string()
    category = self._RNG.choice(AssetCategory)

    # Make the minimum
    req = {"name": name, "category": category}

    result = self.api_post("/api/asset", json=req)
    with p.get_session() as s:
      a = s.query(Asset).first()
      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

      s.delete(a)
      s.commit()
    self.assertDictEqual(target, result)

    # Make the maximum
    description = self.random_string()
    unit = self.random_string()
    tag = self.random_string()
    req = {
        "name": name,
        "description": description,
        "category": category,
        "unit": unit,
        "tag": tag
    }

    result = self.api_post("/api/asset", json=req)
    with p.get_session() as s:
      a = s.query(Asset).first()
      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"name": name}
    self.api_post("/api/asset", json=req, rc=400)

  def test_get(self):
    p = self._portfolio

    # Create accounts
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    # Get by uuid
    result = self.api_get(f"/api/asset/{a_uuid}")
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    # Create accounts
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    # Update by uuid
    new_name = self.random_string()
    new_category = AssetCategory.SECURITY
    target["name"] = new_name
    target["category"] = new_category.name.lower()
    req = dict(target)
    req.pop("uuid")
    result = self.api_put(f"/api/asset/{a_uuid}", json=req)
    with p.get_session() as s:
      a = s.query(Asset).where(Asset.uuid == a_uuid).first()
      self.assertEqual(new_name, a.name)
      self.assertEqual(new_category, a.category)
    self.assertEqual(target, result)

    # Read only properties
    self.api_put(f"/api/asset/{a_uuid}", json=target, rc=400)

  def test_delete(self):
    p = self._portfolio

    # Create accounts
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    n_valuations = 10
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      for _ in range(n_valuations):
        v = AssetValuation(asset=a,
                           value=float(self._RNG.uniform(0, 10)),
                           date=today)
        s.add(v)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    with p.get_session() as s:
      result = s.query(Asset).count()
      self.assertEqual(1, result)
      result = s.query(AssetValuation).count()
      self.assertEqual(n_valuations, result)

    # Delete by uuid
    result = self.api_delete(f"/api/asset/{a_uuid}")
    self.assertEqual(target, result)

    with p.get_session() as s:
      result = s.query(Asset).count()
      self.assertEqual(0, result)
      result = s.query(AssetValuation).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    p = self._portfolio

    # Create assets
    a_banana = Asset(name="Banana",
                     category=AssetCategory.ITEM,
                     unit="bunches",
                     tag="fruit")
    a_banana_inc = Asset(name="BANANA inc.",
                         category=AssetCategory.SECURITY,
                         description="Big 'ole farm")
    with p.get_session() as s:
      s.add_all((a_banana, a_banana_inc))
      s.commit()
      query = s.query(Asset)
      assets = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))

    # Get all
    result = self.api_get("/api/assets")
    target = {"assets": assets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Get only cash
    result = self.api_get("/api/assets", {"category": "item"})
    target = {"assets": assets[:1], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Get via paging
    result = self.api_get("/api/assets", {"limit": 1})
    target = {"assets": assets[:1], "count": 2, "next_offset": 1}
    self.assertEqual(target, result)

    result = self.api_get("/api/assets", {"limit": 1, "offset": 1})
    target = {"assets": assets[1:], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Search by name
    result = self.api_get("/api/assets", {"search": "banana"})
    target = {"assets": assets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Bad search, neither are over the threshold
    result = self.api_get("/api/assets", {"search": "inc"})
    target = {"assets": assets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Search by description
    result = self.api_get("/api/assets", {"search": "farm"})
    target = {"assets": assets[1:], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by unit
    result = self.api_get("/api/assets", {"search": "bunches"})
    target = {"assets": assets[:1], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by tag
    result = self.api_get("/api/assets", {"search": "fruit"})
    target = {"assets": assets[:1], "count": 1, "next_offset": None}
    self.assertEqual(target, result)
