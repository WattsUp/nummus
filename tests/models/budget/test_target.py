from __future__ import annotations

import datetime

import pytest

from nummus import exceptions as exc
from nummus.models import Target, TargetPeriod, TargetType, TransactionCategory


@pytest.mark.xfail
def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)
    TransactionCategory.add_default(s)
    names = TransactionCategory.map_name(s)
    names_rev = {v: k for k, v in names.items()}

    today = datetime.datetime.now().astimezone().date()
    today_ord = today.toordinal()

    d = {
        "category_id": names_rev["general merchandise"],
        "amount": self.random_decimal(1, 10),
        "type_": TargetType.BALANCE,
        "period": TargetPeriod.ONCE,
        "due_date_ord": today_ord,
        "repeat_every": 0,
    }

    t = Target(**d)
    s.add(t)
    s.commit()

    assert t.category_id == d["category_id"]
    assert t.amount == d["amount"]
    assert t.type_ == d["type_"]
    assert t.period == d["period"]
    assert t.due_date_ord == d["due_date_ord"]
    assert t.repeat_every == d["repeat_every"]

    # ONCE cannot be REFILL
    t.type_ = TargetType.REFILL
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # ONCE cannot be ACCUMULATE
    t.type_ = TargetType.ACCUMULATE
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # ONCE cannot repeat
    t.repeat_every = 2
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # BALANCE cannot have a due date
    t.due_date_ord = None
    s.commit()

    # But not ONCE can be those things
    t.period = TargetPeriod.WEEK
    t.type_ = TargetType.ACCUMULATE
    t.repeat_every = 1
    t.due_date_ord = today_ord
    s.commit()

    # WEEK must repeat
    t.repeat_every = 0
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # WEEK can only repeat every week
    t.repeat_every = 2
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # MONTH and YEAR can repeat every other
    t.period = TargetPeriod.MONTH
    t.repeat_every = 2
    s.commit()

    # !ONCE cannot be BALANCE
    t.type_ = TargetType.BALANCE
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # ACCUMULATE must have a due date
    t.due_date_ord = None
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Duplicate category_id are bad
    t = Target(**d)
    s.add(t)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()
