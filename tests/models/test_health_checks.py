from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from tests.conftest import RandomStringGenerator


def test_init_properties(
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "check": rand_str_generator(),
        "value": rand_str_generator(),
        "msg": rand_str_generator(),
        "ignore": False,
    }

    i = HealthCheckIssue.create(**d)

    assert i.check == d["check"]
    assert i.value == d["value"]
    assert i.msg == d["msg"]
    assert i.ignore == d["ignore"]


def test_duplicate_keys(
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "check": rand_str_generator(),
        "value": rand_str_generator(),
        "msg": rand_str_generator(),
        "ignore": False,
    }
    HealthCheckIssue.create(**d)
    with pytest.raises(exc.IntegrityError):
        HealthCheckIssue.create(**d)


def test_short_check(rand_str_generator: RandomStringGenerator) -> None:
    d = {
        "check": "a",
        "value": rand_str_generator(),
        "msg": rand_str_generator(),
        "ignore": False,
    }
    with pytest.raises(exc.InvalidORMValueError):
        HealthCheckIssue.create(**d)


def test_short_value(
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "check": rand_str_generator(),
        "value": "a",
        "msg": rand_str_generator(),
        "ignore": False,
    }
    HealthCheckIssue.create(**d)
