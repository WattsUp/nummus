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
    from tests.conftest import RandomStringGenerator


def test_init_properties(rand_str: str) -> None:
    d = {
        "key": ConfigKey.WEB_KEY,
        "value": rand_str,
    }

    c = Config.create(**d)

    assert c.key == d["key"]
    assert c.value == d["value"]


def test_duplicate_keys(
    rand_str_generator: RandomStringGenerator,
) -> None:
    Config.create(key=ConfigKey.WEB_KEY, value=rand_str_generator())
    with pytest.raises(exc.IntegrityError):
        Config.create(key=ConfigKey.WEB_KEY, value=rand_str_generator())


def test_empty() -> None:
    with pytest.raises(exc.IntegrityError):
        Config.create(key=ConfigKey.WEB_KEY, value="")


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        Config.create(key=ConfigKey.WEB_KEY, value="a")


def test_set(rand_str: str) -> None:
    Config.set_(ConfigKey.VERSION, rand_str)

    v = Config.query(Config.value).where(Config.key == ConfigKey.VERSION).scalar()
    assert v == rand_str


def test_set_new(rand_str: str) -> None:
    Config.set_(ConfigKey.WEB_KEY, rand_str)

    v = Config.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
    assert v == rand_str


def test_fetch() -> None:
    target = Config.query(Config.value).where(Config.key == ConfigKey.VERSION).scalar()
    assert Config.fetch(ConfigKey.VERSION) == target


def test_fetch_missing() -> None:
    with pytest.raises(exc.ProtectedObjectNotFoundError):
        Config.fetch(ConfigKey.WEB_KEY)


def test_fetch_missing_ok() -> None:
    assert Config.fetch(ConfigKey.WEB_KEY, no_raise=True) is None


def test_db_version() -> None:
    target = max(
        Version(__version__),
        *[m.min_version() for m in MIGRATORS],
    )
    assert Config.db_version() == target


def test_base_currency() -> None:
    assert Config.base_currency() == DEFAULT_CURRENCY
