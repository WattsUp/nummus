from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import Target, TargetPeriod, TargetType
from tests import conftest

if TYPE_CHECKING:
    import datetime
    from decimal import Decimal

    from sqlalchemy import orm


def test_init_properties(
    today: datetime.date,
    today_ord: int,
    session: orm.Session,
    rand_real: Decimal,
    categories: dict[str, int],
) -> None:
    d = {
        "category_id": categories["uncategorized"],
        "amount": rand_real,
        "type_": TargetType.BALANCE,
        "period": TargetPeriod.ONCE,
        "due_date_ord": today_ord,
        "repeat_every": 0,
    }

    t = Target(**d)
    session.add(t)
    session.commit()

    assert t.category_id == d["category_id"]
    assert t.amount == d["amount"]
    assert t.type_ == d["type_"]
    assert t.period == d["period"]
    assert t.due_date_ord == d["due_date_ord"]
    assert t.due_date == today
    assert t.repeat_every == d["repeat_every"]


@pytest.mark.parametrize(
    ("period", "type_", "kwargs", "success"),
    [
        (TargetPeriod.ONCE, TargetType.REFILL, {}, False),
        (TargetPeriod.ONCE, TargetType.ACCUMULATE, {}, False),
        (TargetPeriod.ONCE, TargetType.BALANCE, {"repeat_every": 2}, False),
        (TargetPeriod.WEEK, TargetType.REFILL, {"repeat_every": 1}, True),
        (TargetPeriod.WEEK, TargetType.REFILL, {"repeat_every": 0}, False),
        (TargetPeriod.WEEK, TargetType.REFILL, {"repeat_every": 2}, False),
        (TargetPeriod.MONTH, TargetType.REFILL, {"repeat_every": 2}, True),
        (TargetPeriod.YEAR, TargetType.REFILL, {"repeat_every": 2}, True),
        (TargetPeriod.WEEK, TargetType.BALANCE, {}, False),
        (TargetPeriod.MONTH, TargetType.BALANCE, {}, False),
        (TargetPeriod.YEAR, TargetType.BALANCE, {}, False),
        (
            TargetPeriod.WEEK,
            TargetType.REFILL,
            {"repeat_every": 1, "due_date_ord": None},
            False,
        ),
    ],
    ids=conftest.id_func,
)
def test_check_constraints(
    today_ord: int,
    session: orm.Session,
    rand_real: Decimal,
    categories: dict[str, int],
    period: TargetPeriod,
    type_: TargetType,
    kwargs: dict[str, object],
    success: bool,
) -> None:
    d = {
        "category_id": categories["uncategorized"],
        "amount": rand_real,
        "type_": type_,
        "period": period,
        "due_date_ord": today_ord,
        "repeat_every": 0,
    }
    d.update(kwargs)
    t = Target(**d)
    session.add(t)
    if success:
        session.commit()
    else:
        with pytest.raises(exc.IntegrityError):
            session.commit()


def test_duplicates(
    today_ord: int,
    session: orm.Session,
    rand_real: Decimal,
    categories: dict[str, int],
) -> None:
    d = {
        "category_id": categories["uncategorized"],
        "amount": rand_real,
        "type_": TargetType.BALANCE,
        "period": TargetPeriod.ONCE,
        "due_date_ord": today_ord,
        "repeat_every": 0,
    }

    t = Target(**d)
    session.add(t)
    t = Target(**d)
    session.add(t)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_date_none(
    session: orm.Session,
    rand_real: Decimal,
    categories: dict[str, int],
) -> None:
    d = {
        "category_id": categories["uncategorized"],
        "amount": rand_real,
        "type_": TargetType.BALANCE,
        "period": TargetPeriod.ONCE,
        "due_date_ord": None,
        "repeat_every": 0,
    }

    t = Target(**d)
    session.add(t)

    assert t.due_date is None
