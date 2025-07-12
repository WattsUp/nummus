from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.config import Config, ConfigKey

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator


def test_init_properties(session: orm.Session, rand_str: str) -> None:
    d = {
        "key": ConfigKey.WEB_KEY,
        "value": rand_str,
    }

    c = Config(**d)
    session.add(c)
    session.commit()

    assert c.key == d["key"]
    assert c.value == d["value"]


def test_duplicate_keys(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    c = Config(key=ConfigKey.WEB_KEY, value=rand_str_generator())
    session.add(c)
    c = Config(key=ConfigKey.WEB_KEY, value=rand_str_generator())
    session.add(c)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_empty(session: orm.Session) -> None:
    c = Config(key=ConfigKey.WEB_KEY, value="")
    session.add(c)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        Config(key=ConfigKey.WEB_KEY, value="a")
