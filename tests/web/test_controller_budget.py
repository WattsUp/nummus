"""Test module nummus.web.controller_budget
"""

import datetime
import json
from nummus.models import Budget, NummusJSONEncoder

from tests.web.base import WebTestBase


class TestControllerBudget(WebTestBase):
  """Test controller_budget methods
  """

  def test_create(self):
    p = self._portfolio

    date = datetime.date.today()
    home = float(self._RNG.uniform(0, 100))
    food = float(self._RNG.uniform(0, 100))
    shopping = float(self._RNG.uniform(0, 100))
    hobbies = float(self._RNG.uniform(0, 100))
    services = float(self._RNG.uniform(0, 100))
    travel = float(self._RNG.uniform(0, 100))

    # Make the minimum
    req = {
        "date": date,
        "categories": {
            "home": home,
            "food": food,
            "shopping": shopping,
            "hobbies": hobbies,
            "services": services,
            "travel": travel
        }
    }

    response = self.api_post("/api/budget", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    with p.get_session() as s:
      a = s.query(Budget).first()
      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

      s.delete(a)
      s.commit()

    result = response.json
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"date": date}
    response = self.api_post("/api/budget", json=req)
    self.assertEqual(400, response.status_code)

  def test_get(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = b.uuid
      target = json.loads(json.dumps(b, cls=NummusJSONEncoder))

    # Get by uuid
    response = self.api_get(f"/api/budget/{b_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = b.uuid
      target = json.loads(json.dumps(b, cls=NummusJSONEncoder))

    # Update by uuid
    new_date = today - datetime.timedelta(days=1)
    new_home = float(self._RNG.uniform(0, 100))
    target["date"] = new_date.isoformat()
    target["categories"]["home"] = new_home
    target["total"] = new_home
    req = dict(target)
    req.pop("uuid")
    req.pop("total")
    response = self.api_put(f"/api/budget/{b_uuid}", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    with p.get_session() as s:
      b = s.query(Budget).where(Budget.uuid == b_uuid).first()
      self.assertEqual(new_date, b.date)
      self.assertEqualWithinError(new_home, b.home, 1e-6)
    result = response.json
    self.assertEqual(target, result)

    # Read only properties
    response = self.api_put(f"/api/budget/{b_uuid}", json=target)
    self.assertEqual(400, response.status_code)

  def test_delete(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = b.uuid
      target = json.loads(json.dumps(b, cls=NummusJSONEncoder))

    with p.get_session() as s:
      result = s.query(Budget).count()
      self.assertEqual(1, result)

    # Delete by uuid
    response = self.api_delete(f"/api/budget/{b_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

    with p.get_session() as s:
      result = s.query(Budget).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

    # Get all
    response = self.api_get("/api/budgets")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Budget)
      budgets = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    target = {"budgets": budgets}
    self.assertEqual(target, result)
