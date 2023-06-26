"""Test module nummus.models.budget
"""

import datetime

from nummus import models
from nummus.models import budget

from tests.base import TestBase


class TestAnnualBudget(TestBase):
  """Test AnnualBudget class
  """

  def test_init_properties(self):
    session = self._get_session()
    models.metadata_create_all(session)

    today = datetime.date.today()

    b = budget.AnnualBudget(date=today)
    session.add(b)
    session.commit()

    # Default to 0
    self.assertEqual(today, b.date)
    self.assertEqual(0, b.home)
    self.assertEqual(0, b.food)
    self.assertEqual(0, b.shopping)
    self.assertEqual(0, b.hobbies)
    self.assertEqual(0, b.services)
    self.assertEqual(0, b.travel)

    d = {
        "date": datetime.date.today(),
        "home": self._RNG.uniform(0, 1),
        "food": self._RNG.uniform(0, 1),
        "shopping": self._RNG.uniform(0, 1),
        "hobbies": self._RNG.uniform(0, 1),
        "services": self._RNG.uniform(0, 1),
        "travel": self._RNG.uniform(0, 1)
    }

    b = budget.AnnualBudget(**d)
    session.add(b)
    session.commit()

    self.assertEqual(d["date"], b.date)
    self.assertEqual(d["home"], b.home)
    self.assertEqual(d["food"], b.food)
    self.assertEqual(d["shopping"], b.shopping)
    self.assertEqual(d["hobbies"], b.hobbies)
    self.assertEqual(d["services"], b.services)
    self.assertEqual(d["travel"], b.travel)

    d.pop("date")
    total = sum(d.values())
    self.assertEqualWithinError(total, b.total, 1e-6)

    self.assertDictEqual(d, b.categories)

    target = {"id": b.id, "date": b.date, "total": total, "categories": d}
    result = b.to_dict()
    self.assertDictEqual(target, result)

  def test_set_categories(self):
    session = self._get_session()
    models.metadata_create_all(session)

    today = datetime.date.today()

    b = budget.AnnualBudget(date=today)
    session.add(b)
    session.commit()

    self.assertRaises(KeyError, setattr, b, "categories", {})
    self.assertRaises(KeyError, setattr, b, "categories", {"home": 1})

    d = {
        "hobbies": self._RNG.uniform(0, 1),
        "services": self._RNG.uniform(0, 1),
        "travel": self._RNG.uniform(0, 1),
        "home": self._RNG.uniform(0, 1),
        "food": self._RNG.uniform(0, 1),
        "shopping": self._RNG.uniform(0, 1)
    }
    b.categories = d

    self.assertEqual(d["home"], b.home)
    self.assertEqual(d["food"], b.food)
    self.assertEqual(d["shopping"], b.shopping)
    self.assertEqual(d["hobbies"], b.hobbies)
    self.assertEqual(d["services"], b.services)
    self.assertEqual(d["travel"], b.travel)

    d["fake"] = 1
    self.assertRaises(KeyError, setattr, b, "categories", d)
