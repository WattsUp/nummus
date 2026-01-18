from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from packaging.version import Version

from nummus import exceptions as exc
from nummus.migrations.top import MIGRATORS
from nummus.models.config import Config, ConfigKey
from nummus.models.currency import DEFAULT_CURRENCY
from nummus.version import __version__

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


def test_set(session: orm.Session, rand_str: str) -> None:
    Config.set_(session, ConfigKey.WEB_KEY, rand_str)
    session.commit()

    v = session.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
    assert v == rand_str


def test_fetch(session: orm.Session) -> None:
    target = session.query(Config.value).where(Config.key == ConfigKey.VERSION).scalar()
    assert Config.fetch(session, ConfigKey.VERSION) == target


def test_fetch_missing(session: orm.Session) -> None:
    with pytest.raises(exc.ProtectedObjectNotFoundError):
        Config.fetch(session, ConfigKey.WEB_KEY)


def test_fetch_missing_ok(session: orm.Session) -> None:
    assert Config.fetch(session, ConfigKey.WEB_KEY, no_raise=True) is None


def test_db_version(session: orm.Session) -> None:
    target = max(
        Version(__version__),
        *[m.min_version() for m in MIGRATORS],
    )
    assert Config.db_version(session) == target


def test_base_currency(session: orm.Session) -> None:
    assert Config.base_currency(session) == DEFAULT_CURRENCY
