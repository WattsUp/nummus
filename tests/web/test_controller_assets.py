"""Test module nummus.web.controller_assets
"""

import datetime
import json

from nummus.models import (Asset, AssetCategory, AssetValuation,
                           NummusJSONEncoder)

from tests.web.base import WebTestBase


class TestControllerAssets(WebTestBase):
  """Test controller_assets methods
  """

  def test_create(self):
    p = self._portfolio

    name = self.random_string()
    category = self._RNG.choice(AssetCategory)

    # Make the minimum
    req = {"name": name, "category": category}
    endpoint = "/api/assets"
    result, headers = self.api_post(endpoint, json=req)
    with p.get_session() as s:
      a = s.query(Asset).first()
      self.assertEqual(f"/api/assets/{a.uuid}", headers["Location"])

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

    result, headers = self.api_post(endpoint, json=req)
    with p.get_session() as s:
      a = s.query(Asset).first()
      self.assertEqual(f"/api/assets/{a.uuid}", headers["Location"])

      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"name": name}
    self.api_post(endpoint, json=req, rc=400)

  def test_get(self):
    p = self._portfolio

    # Create assets
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))
    endpoint = f"/api/assets/{a_uuid}"

    # Get by uuid
    result, _ = self.api_get(endpoint)
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    # Create assets
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
    result, _ = self.api_put(f"/api/assets/{a_uuid}", json=req)
    with p.get_session() as s:
      a = s.query(Asset).where(Asset.uuid == a_uuid).first()
      self.assertEqual(new_name, a.name)
      self.assertEqual(new_category, a.category)
    self.assertEqual(target, result)

    # Read only properties
    self.api_put(f"/api/assets/{a_uuid}", json=target, rc=400)

  def test_delete(self):
    p = self._portfolio

    # Create assets
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

    with p.get_session() as s:
      result = s.query(Asset).count()
      self.assertEqual(1, result)
      result = s.query(AssetValuation).count()
      self.assertEqual(n_valuations, result)

    # Delete by uuid
    self.api_delete(f"/api/assets/{a_uuid}")

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
    endpoint = "/api/assets"

    # Get all
    result, _ = self.api_get(endpoint)
    target = {"assets": assets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Get only cash
    result, _ = self.api_get(endpoint, {"category": "item"})
    target = {"assets": [assets[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Get via paging
    result, _ = self.api_get(endpoint, {"limit": 1})
    target = {"assets": [assets[0]], "count": 2, "next_offset": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"limit": 1, "offset": 1})
    target = {"assets": [assets[1]], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Search by name
    result, _ = self.api_get(endpoint, {"search": "banana"})
    target = {"assets": assets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Bad search, neither are over the threshold
    result, _ = self.api_get(endpoint, {"search": "inc"})
    target = {"assets": assets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Search by description
    result, _ = self.api_get(endpoint, {"search": "farm"})
    target = {"assets": [assets[1]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by unit
    result, _ = self.api_get(endpoint, {"search": "bunches"})
    target = {"assets": [assets[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by tag
    result, _ = self.api_get(endpoint, {"search": "fruit"})
    target = {"assets": [assets[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Bad enum
    self.api_get(endpoint, {"category": "fruit"}, rc=400)

    # Bad limit type
    self.api_get(endpoint, {"limit": "ten"}, rc=400)

  def test_get_image(self):
    p = self._portfolio

    # Create assets
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
    endpoint = f"/api/assets/{a_uuid}/image"

    # No image
    self.api_get(endpoint, rc=404)

    path_img = p.image_path.joinpath(f"{a_uuid}.png")
    with p.get_session() as s:
      a = s.query(Asset).first()
      a.img_suffix = path_img.suffix
      s.commit()

    # Still no image
    self.api_get(endpoint, rc=404)

    fake_image = self.random_string().encode()
    with open(path_img, "wb") as file:
      file.write(fake_image)

    result, _ = self.api_get(endpoint, content_type="image/png")
    self.assertEqual(fake_image, result)

  def test_update_image(self):
    p = self._portfolio

    suffix = ".png"
    fake_image = self.random_string().encode()

    # Create assets
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
    endpoint = f"/api/assets/{a_uuid}/image"

    self.api_put(endpoint,
                 data=fake_image,
                 headers={"Content-Type": "image/png"},
                 rc=204)

    with p.get_session() as s:
      a = s.query(Asset).first()
      self.assertEqual(suffix, a.img_suffix)

      path_img = p.image_path.joinpath(a.image_name)

    with open(path_img, "rb") as file:
      buf = file.read()
      self.assertEqual(fake_image, buf)

    # Missing length
    self.api_put(endpoint, rc=411)

    # Too long
    self.api_put(endpoint,
                 data="a" * 1000001,
                 headers={"Content-Type": "image/png"},
                 rc=413)

    # Bad type
    self.api_put(endpoint,
                 data=fake_image,
                 headers={"Content-Type": "application/pdf"},
                 rc=415)

    # Missing type
    self.api_put(endpoint, data=fake_image, headers={}, rc=422)

  def test_delete_image(self):
    p = self._portfolio

    suffix = ".png"
    fake_image = self.random_string().encode()

    # Create assets
    a = Asset(name="BANANA", category=AssetCategory.ITEM, img_suffix=suffix)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
    endpoint = f"/api/assets/{a_uuid}/image"

    path_img = p.image_path.joinpath(a.image_name)
    with open(path_img, "wb") as file:
      file.write(fake_image)

    self.api_delete(endpoint)

    with p.get_session() as s:
      a = s.query(Asset).first()
      self.assertIsNone(a.img_suffix)

    self.assertFalse(path_img.exists())

    # Doesn't exist anymore
    self.api_delete(endpoint, rc=404)

    # If img_suffix is set but image is gone, clean up img_suffix
    with p.get_session() as s:
      a = s.query(Asset).first()
      a.img_suffix = path_img.suffix
      s.commit()

      self.api_delete(endpoint)

      self.assertIsNone(a.img_suffix)

  def test_get_value(self):
    p = self._portfolio

    # Create accounts
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      v_today = AssetValuation(asset=a,
                               date=today,
                               value=self._RNG.uniform(-1, 1))
      v_before = AssetValuation(asset=a,
                                date=today - datetime.timedelta(days=2),
                                value=self._RNG.uniform(-1, 1))
      v_after = AssetValuation(asset=a,
                               date=today + datetime.timedelta(days=2),
                               value=self._RNG.uniform(-1, 1))
      s.add_all((v_today, v_before, v_after))
      s.commit()

      a_uuid = a.uuid

      target_dates = [(today + datetime.timedelta(days=i)).isoformat()
                      for i in range(-3, 3 + 1)]
      target_values = [
          0, v_before.value, v_before.value, v_today.value, v_today.value,
          v_after.value, v_after.value
      ]
      start = target_dates[0]
      end = target_dates[-1]

    endpoint = f"/api/assets/{a_uuid}/value"

    # Default to today's value
    result, _ = self.api_get(endpoint)
    target = {"dates": [target_dates[3]], "values": [target_values[3]]}
    self.assertEqual(target, result)

    # Default to today's value
    result, _ = self.api_get(endpoint, {"start": start, "end": end})
    target = {"dates": target_dates, "values": target_values}
    self.assertEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": end, "end": start}, rc=422)
