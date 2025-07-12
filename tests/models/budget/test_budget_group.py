from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import BudgetGroup

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator


def test_init_properties(session: orm.Session, rand_str: str) -> None:
    d = {
        "name": rand_str,
        "position": 0,
    }
    g = BudgetGroup(**d)
    session.add(g)
    session.commit()

    assert g.name == d["name"]
    assert g.position == d["position"]


def test_duplicate_names(
    session: orm.Session,
    rand_str: str,
) -> None:
    g = BudgetGroup(name=rand_str, position=0)
    session.add(g)
    g = BudgetGroup(name=rand_str, position=1)
    session.add(g)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_duplicate_position(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    g = BudgetGroup(name=rand_str_generator(), position=0)
    session.add(g)
    g = BudgetGroup(name=rand_str_generator(), position=0)
    session.add(g)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_empty(session: orm.Session) -> None:
    g = BudgetGroup(name="", position=0)
    session.add(g)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        BudgetGroup(name="a", position=0)
