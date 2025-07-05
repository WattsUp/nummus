from __future__ import annotations

import datetime
import random
import shutil
import string

import pytest
from sqlalchemy import orm

from nummus import global_config, sql
from nummus.models import base_uri
from nummus.portfolio import Portfolio


def id_func(val: object) -> str | None:
    if isinstance(val, datetime.date):
        return val.isoformat()
    return None


class RandomStringGenerator:

    @classmethod
    def __call__(cls, length: int = 20) -> str:
        return "".join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture(scope="session")
def rand_str_generator() -> RandomStringGenerator:
    """Returns a random string generator.

    Returns:
        RandomString generator
    """
    return RandomStringGenerator()


@pytest.fixture
def rand_str(rand_str_generator: RandomStringGenerator) -> str:
    """Returns a random string.

    Returns:
        RandomString generator
    """
    return rand_str_generator()


class EmptyPortfolioGenerator:

    def __init__(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        # Create the portfolio once, then copy the file each time called
        self._path = tmp_path_factory.mktemp("data") / "portfolio.db"
        Portfolio.create(self._path)

    def __call__(self) -> Portfolio:
        tmp_path = self._path.with_suffix(".tmp.db")
        shutil.copyfile(self._path, tmp_path)
        return Portfolio(tmp_path, None)


@pytest.fixture(scope="session")
def empty_portfolio_generator(
    tmp_path_factory: pytest.TempPathFactory,
) -> EmptyPortfolioGenerator:
    """Returns an empty portfolio generator.

    Returns:
        EmptyPortfolio generator
    """
    return EmptyPortfolioGenerator(tmp_path_factory)


@pytest.fixture
def empty_portfolio(empty_portfolio_generator: EmptyPortfolioGenerator) -> Portfolio:
    """Returns an empty portfolio.

    Returns:
        Portfolio
    """
    return empty_portfolio_generator()


@pytest.fixture(autouse=True)
def uri_cipher() -> None:
    """Generate a URI cipher."""
    base_uri._CIPHER = base_uri.Cipher.generate()  # noqa: SLF001


@pytest.fixture(autouse=True)
def clear_config_cache() -> None:
    """Clear global config cache."""
    global_config._CACHE.clear()  # noqa: SLF001


@pytest.fixture
def today() -> datetime.date:
    """Get today's date.

    Returns:
        today datetime.date
    """
    return datetime.datetime.now().astimezone().date()


@pytest.fixture
def session(empty_portfolio_generator: EmptyPortfolioGenerator) -> orm.Session:
    """Create SQL session.

    Returns:
        Session generator
    """
    return orm.Session(sql.get_engine(empty_portfolio_generator().path, None))
