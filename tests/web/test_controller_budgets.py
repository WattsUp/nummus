"""Test module nummus.web.controller_budgets
"""

import typing as t

import datetime
import json
from nummus.models import Budget, NummusJSONEncoder

from tests.web.base import WebTestBase


class TestControllerBudgets(WebTestBase):
  """Test controller_budgets methods
  """

  def test_create(self):
    p = self._portfolio

    date = datetime.date.today()
    home = self.random_decimal(-100, 0)
    food = self.random_decimal(-100, 0)
    shopping = self.random_decimal(-100, 0)
    hobbies = self.random_decimal(-100, 0)
    services = self.random_decimal(-100, 0)
    travel = self.random_decimal(-100, 0)

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
    endpoint = "/api/budgets"
    result, headers = self.api_post(endpoint, json=req)
    with p.get_session() as s:
      b = s.query(Budget).first()
      b_uuid = b.uuid
      self.assertEqual(f"/api/budgets/{b_uuid}", headers["Location"])
      s.delete(b)
      s.commit()

    target = dict(req)
    target["uuid"] = b_uuid
    target["date"] = str(target["date"])
    target["total"] = sum(target["categories"].values())
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"date": date}
    self.api_post(endpoint, json=req, rc=400)

    # Wrong Content-Type
    self.api_post(endpoint,
                  data="raw",
                  headers={"Content-Type": "text/plain"},
                  rc=415)

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
    endpoint = f"/api/budgets/{b_uuid}"

    # Get by uuid
    result, _ = self.api_get(endpoint)
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
    endpoint = f"/api/budgets/{b_uuid}"

    # Update by uuid
    new_date = today - datetime.timedelta(days=1)
    new_home = self.random_decimal(-100, 0)
    target["date"] = new_date.isoformat()
    target["categories"]["home"] = new_home
    target["total"] = new_home
    req = dict(target)
    req.pop("uuid")
    req.pop("total")
    result, _ = self.api_put(endpoint, json=req)
    with p.get_session() as s:
      b = s.query(Budget).where(Budget.uuid == b_uuid).first()
      self.assertEqual(new_date, b.date)
      self.assertEqual(new_home, b.home)
    self.assertEqual(target, result)

    # Read only properties
    self.api_put(endpoint, json=target, rc=400)

    # Wrong Content-Type
    self.api_put(endpoint,
                 data="raw",
                 headers={"Content-Type": "text/plain"},
                 rc=415)

  def test_delete(self):
    p = self._portfolio

    # Create budget
    today = datetime.date.today()
    b = Budget(date=today)
    with p.get_session() as s:
      s.add(b)
      s.commit()

      b_uuid = b.uuid
    endpoint = f"/api/budgets/{b_uuid}"

    with p.get_session() as s:
      result = s.query(Budget).count()
      self.assertEqual(1, result)

    # Delete by uuid
    self.api_delete(endpoint)

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
      budgets: t.List[t.Dict[str, object]] = json.loads(
          json.dumps(query.all(), cls=NummusJSONEncoder))
    endpoint = "/api/budgets"

    # Get all
    result, _ = self.api_get(endpoint)
    target = {"budgets": budgets, "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Sort by newest first
    result, _ = self.api_get(endpoint, {"sort": "newest"})
    target = {"budgets": budgets[::-1], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Get via paging
    result, _ = self.api_get(endpoint, {"limit": 1})
    target = {"budgets": budgets[:1], "count": 2, "next_offset": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"limit": 1, "offset": 1})
    target = {"budgets": budgets[1:], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Get via paging reverse
    result, _ = self.api_get(endpoint, {"limit": 1, "sort": "newest"})
    target = {"budgets": budgets[1:], "count": 2, "next_offset": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {
        "limit": 1,
        "offset": 1,
        "sort": "newest"
    })
    target = {"budgets": budgets[:1], "count": 2, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by start date
    result, _ = self.api_get(endpoint, {"start": today, "end": tomorrow})
    target = {"budgets": budgets[1:], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by end date
    result, _ = self.api_get(endpoint, {"end": yesterday})
    target = {"budgets": budgets[:1], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Strict query validation
    self.api_get(endpoint, {"limit": "invalid"}, rc=400)
