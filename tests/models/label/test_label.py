from __future__ import annotations

import pytest

from nummus import exceptions as exc
from nummus.models.label import Label


def test_init_properties(rand_str: str) -> None:
    d = {"name": rand_str}

    label = Label.create(**d)

    assert label.name == d["name"]


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        Label(name="a")
