from __future__ import annotations

import random
import shutil
import string

import pytest

from nummus.portfolio import Portfolio


class RandomString:

    @classmethod
    def __call__(cls, length: int = 20) -> str:
        return "".join(random.choice(string.ascii_letters) for _ in range(length))


@pytest.fixture
def rand_str() -> RandomString:
    """Returns a random string generator.

    Returns:
        RandomString generator
    """
    return RandomString()


class EmptyPortfolio:

    def __init__(self, tmp_path_factory: pytest.TempPathFactory) -> None:
        # Create the portfolio once, then copy the file each time called
        self._path = tmp_path_factory.mktemp("data") / "portfolio.db"
        Portfolio.create(self._path)

    def __call__(self) -> Portfolio:
        tmp_path = self._path.with_suffix(".tmp.db")
        shutil.copyfile(self._path, tmp_path)
        return Portfolio(tmp_path, None)


@pytest.fixture(scope="session")
def empty_portfolio(tmp_path_factory: pytest.TempPathFactory) -> EmptyPortfolio:
    """Returns an empty portfolio.

    Returns:
        EmptyPortfolio generator
    """
    return EmptyPortfolio(tmp_path_factory)
