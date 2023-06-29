"""Test module nummus.web.controller_asset
"""

import datetime
import io
import json
from unittest import mock
import warnings

from nummus import portfolio
from nummus.models import (Asset, AssetCategory, AssetValuation,
                           NummusJSONEncoder)

from tests.base import TestBase


class TestControllerAsset(TestBase):
  """Test controller_asset methods
  """

  def test_create(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    name = self.random_string()
    category = self._RNG.choice(AssetCategory)

    # Make the minimum
    req = {"name": name, "category": category}

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.post("/api/asset", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    with p.get_session() as s:
      a = s.query(Asset).first()
      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

      s.delete(a)
      s.commit()

    result = response.json
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

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.post("/api/asset", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    with p.get_session() as s:
      a = s.query(Asset).first()
      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    result = response.json
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"name": name}
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.post("/api/asset", json=req)
    self.assertEqual(400, response.status_code)

  def test_get(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts
    a = Asset(name="BANANA", category=AssetCategory.ITEM)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    # Get by uuid
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get(f"/api/asset/{a_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

  def test_update(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

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
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.put(f"/api/asset/{a_uuid}", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    with p.get_session() as s:
      a = s.query(Asset).where(Asset.uuid == a_uuid).first()
      self.assertEqual(new_name, a.name)
      self.assertEqual(new_category, a.category)
    result = response.json
    self.assertEqual(target, result)

    # Read only properties
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.put(f"/api/asset/{a_uuid}", json=target)
    self.assertEqual(400, response.status_code)

  def test_delete(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

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
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.delete(f"/api/asset/{a_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

    with p.get_session() as s:
      result = s.query(Asset).count()
      self.assertEqual(0, result)
      result = s.query(AssetValuation).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts
    a_banana = Asset(name="Banana", category=AssetCategory.ITEM, unit="bunches")
    a_banana_inc = Asset(name="BANANA", category=AssetCategory.SECURITY)
    with p.get_session() as s:
      s.add_all((a_banana, a_banana_inc))
      s.commit()

    # Get all
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/assets")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Asset)
      accounts = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    target = {"assets": accounts}
    self.assertEqual(target, result)

    # Get only cash
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/assets?category=item")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Asset).where(Asset.category == AssetCategory.ITEM)
      accounts = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    target = {"assets": accounts}
    self.assertEqual(target, result)
