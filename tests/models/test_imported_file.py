from __future__ import annotations

import pytest

from nummus import exceptions as exc
from nummus.models.imported_file import ImportedFile


def test_init_properties(
    rand_str: str,
    today_ord: int,
) -> None:
    f = ImportedFile.create(hash_=rand_str)

    # Default date is today
    assert f.date_ord == today_ord
    assert f.hash_ == rand_str


def test_duplicates(rand_str: str) -> None:
    ImportedFile.create(hash_=rand_str)
    with pytest.raises(exc.IntegrityError):
        ImportedFile.create(hash_=rand_str)
