from __future__ import annotations

import datetime
from decimal import Decimal

import sqlalchemy.exc

from nummus import models
from nummus.models import budget
from tests.base import TestBase


class TestBudget(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()

        d = {"date": today, "amount": self.random_decimal(-1, 0)}

        b = budget.Budget(**d)
        s.add(b)
        s.commit()

        self.assertEqual(b.date, d["date"])
        self.assertEqual(b.amount, d["amount"])

        # Positive amounts are bad
        b.amount = Decimal(1)
        self.assertRaises(sqlalchemy.exc.IntegrityError, s.commit)
        s.rollback()

        # Duplicate dates are bad
        b = budget.Budget(date=today, amount=0)
        s.add(b)
        self.assertRaises(sqlalchemy.exc.IntegrityError, s.commit)
        s.rollback()
