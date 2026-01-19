from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.budget import BudgetGroup

if TYPE_CHECKING:
    from tests.conftest import RandomStringGenerator


def test_init_properties(rand_str: str) -> None:
    d = {
        "name": rand_str,
        "position": 0,
    }
    g = BudgetGroup.create(**d)

    assert g.name == d["name"]
    assert g.position == d["position"]


def test_duplicate_names(
    rand_str: str,
) -> None:
    BudgetGroup.create(name=rand_str, position=0)
    with pytest.raises(exc.IntegrityError):
        BudgetGroup.create(name=rand_str, position=0)


def test_duplicate_position(
    rand_str_generator: RandomStringGenerator,
) -> None:
    BudgetGroup.create(name=rand_str_generator(), position=0)
    with pytest.raises(exc.IntegrityError):
        BudgetGroup.create(name=rand_str_generator(), position=0)


def test_empty() -> None:
    with pytest.raises(exc.IntegrityError):
        BudgetGroup.create(name="", position=0)


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        BudgetGroup.create(name="a", position=0)
