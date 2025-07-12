from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator


def test_init_properties(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "check": rand_str_generator(),
        "value": rand_str_generator(),
        "msg": rand_str_generator(),
        "ignore": False,
    }

    i = HealthCheckIssue(**d)
    session.add(i)
    session.commit()

    assert i.check == d["check"]
    assert i.value == d["value"]
    assert i.msg == d["msg"]
    assert i.ignore == d["ignore"]


def test_duplicate_keys(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "check": rand_str_generator(),
        "value": rand_str_generator(),
        "msg": rand_str_generator(),
        "ignore": False,
    }
    i = HealthCheckIssue(**d)
    session.add(i)
    i = HealthCheckIssue(**d)
    session.add(i)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_short_check(rand_str_generator: RandomStringGenerator) -> None:
    d = {
        "check": "a",
        "value": rand_str_generator(),
        "msg": rand_str_generator(),
        "ignore": False,
    }
    with pytest.raises(exc.InvalidORMValueError):
        HealthCheckIssue(**d)


def test_short_value(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "check": rand_str_generator(),
        "value": "a",
        "msg": rand_str_generator(),
        "ignore": False,
    }
    i = HealthCheckIssue(**d)
    session.add(i)
    session.commit()
