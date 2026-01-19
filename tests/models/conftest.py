from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy import orm


@pytest.fixture(autouse=True)
def session(session: Generator[orm.Session]) -> Generator[orm.Session]:
    return session
