"""Test module nummus.models.budget
"""

import datetime

import sqlalchemy.exc

from nummus import models
from nummus.models import budget

from tests.base import TestBase


class TestBudget(TestBase):
  """Test Budget class
  """

  def test_init_properties(self):
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.date.today()

    d = {"date": today, "total": self.random_decimal(-1, 0)}

    b = budget.Budget(**d)
    s.add(b)
    s.commit()

    self.assertEqual(d["date"], b.date)
    self.assertEqual(d["total"], b.total)

    # Positive amounts are bad
    self.assertRaises(ValueError, setattr, b, "total", 1)

    # Duplicate dates are bad
    b = budget.Budget(date=today, total=0)
    s.add(b)
    self.assertRaises(sqlalchemy.exc.IntegrityError, s.commit)
    s.rollback()
