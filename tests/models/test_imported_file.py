from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import imported_file

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_init_properties(
    session: orm.Session,
    rand_str: str,
    today_ord: int,
) -> None:
    f = imported_file.ImportedFile(hash_=rand_str)
    session.add(f)
    session.commit()

    # Default date is today
    assert f.date_ord == today_ord
    assert f.hash_ == rand_str


def test_duplicates(session: orm.Session, rand_str: str) -> None:
    f = imported_file.ImportedFile(hash_=rand_str)
    session.add(f)
    f = imported_file.ImportedFile(hash_=rand_str)
    session.add(f)
    with pytest.raises(exc.IntegrityError):
        session.commit()
