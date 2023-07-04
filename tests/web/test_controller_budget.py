"""Test module nummus.web.controller_budget
"""

from typing import Dict, List

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

    result, headers = self.api_post("/api/budget", json=req)
    with p.get_session() as s:
      b = s.query(Budget).first()
      self.assertEqual(f"/api/budget/{b.uuid}", headers["Location"])

      # Serialize then deserialize
      target = json.loads(json.dumps(b, cls=NummusJSONEncoder))

      s.delete(b)
      s.commit()
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"date": date}
    self.api_post("/api/budget", json=req, rc=400)

  def test_get(self):
    p = self._portfolio

    # Create budgets
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = b.uuid
      target = json.loads(json.dumps(b, cls=NummusJSONEncoder))

    # Get by uuid
    result, _ = self.api_get(f"/api/budget/{b_uuid}")
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
    result, _ = self.api_put(f"/api/budget/{b_uuid}", json=req)
    with p.get_session() as s:
      b = s.query(Budget).where(Budget.uuid == b_uuid).first()
      self.assertEqual(new_date, b.date)
      self.assertEqualWithinError(new_home, b.home, 1e-6)
    self.assertEqual(target, result)

    # Read only properties
    self.api_put(f"/api/budget/{b_uuid}", json=target, rc=400)

  def test_delete(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = b.uuid

    with p.get_session() as s:
      result = s.query(Budget).count()
      self.assertEqual(1, result)

    # Delete by uuid
    self.api_delete(f"/api/budget/{b_uuid}")

    with p.get_session() as s:
      result = s.query(Budget).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    b_today = Budget(date=today)
    b_yesterday = Budget(date=yesterday)
    with p.get_session() as s:
      s.add_all((b_today, b_yesterday))
      s.commit()
      query = s.query(Budget).order_by(Budget.date)
      budgets: List[Dict[str, object]] = json.loads(
          json.dumps(query.all(), cls=NummusJSONEncoder))

    # Get all
    result, _ = self.api_get("/api/budgets")
    target = {"budgets": budgets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Sort by newest first
    result, _ = self.api_get("/api/budgets", {"sort": "newest"})
    target = {"budgets": budgets[::-1], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Get via paging
    result, _ = self.api_get("/api/budgets", {"limit": 1})
    target = {"budgets": budgets[:1], "count": 2, "next_offset": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get("/api/budgets", {"limit": 1, "offset": 1})
    target = {"budgets": budgets[1:], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Get via paging reverse
    result, _ = self.api_get("/api/budgets", {"limit": 1, "sort": "newest"})
    target = {"budgets": budgets[1:], "count": 2, "next_offset": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get("/api/budgets", {
        "limit": 1,
        "offset": 1,
        "sort": "newest"
    })
    target = {"budgets": budgets[:1], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by start date
    result, _ = self.api_get("/api/budgets", {"start": today, "end": tomorrow})
    target = {"budgets": budgets[1:], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by end date
    result, _ = self.api_get("/api/budgets", {"end": yesterday})
    target = {"budgets": budgets[:1], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Invalid date filters
    self.api_get("/api/budgets", {"start": today, "end": yesterday}, rc=422)

    # Strict query validation
    self.api_get("/api/budgets", {"fake": "invalid"}, rc=400)
