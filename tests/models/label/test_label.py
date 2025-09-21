from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import Label

if TYPE_CHECKING:

    from sqlalchemy import orm


def test_init_properties(session: orm.Session, rand_str: str) -> None:
    d = {"name": rand_str}

    label = Label(**d)
    session.add(label)
    session.commit()

    assert label.name == d["name"]


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        Label(name="a")
