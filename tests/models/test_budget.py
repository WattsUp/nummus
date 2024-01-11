from __future__ import annotations

import datetime
from decimal import Decimal

from nummus import exceptions as exc
from nummus import models
from nummus.models import budget
from tests.base import TestBase


class TestBudget(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        models.metadata_create_all(s)

        today = datetime.date.today()
        today_ord = today.toordinal()

        d = {
            "date_ord": today_ord,
            "amount": self.random_decimal(-1, 0),
        }

        b = budget.Budget(**d)
        s.add(b)
        s.commit()

        self.assertEqual(b.date_ord, d["date_ord"])
        self.assertEqual(b.amount, d["amount"])

        # Positive amounts are bad
        b.amount = Decimal(1)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()

        # Duplicate dates are bad
        b = budget.Budget(date_ord=today_ord, amount=0)
        s.add(b)
        self.assertRaises(exc.IntegrityError, s.commit)
        s.rollback()
