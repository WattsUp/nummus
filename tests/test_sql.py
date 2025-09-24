from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import orm

from nummus import encryption, sql

if TYPE_CHECKING:
    from pathlib import Path


class ORMBase(orm.DeclarativeBase):

    id_: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    def __repr__(self) -> str:
        try:
            return f"<{self.__class__.__name__} id={self.id_}>"
        except orm.exc.DetachedInstanceError:
            return f"<{self.__class__.__name__} id=Detached Instance>"


class Child(ORMBase):
    __tablename__ = "child"


def test_get_engine_unencrypted(tmp_path: Path) -> None:
    # Absolute file
    path = (tmp_path / "absolute.db").absolute()
    e = sql.get_engine(path)
    s = orm.Session(e)
    assert "child" in ORMBase.metadata.tables
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()
    with path.open("rb") as file:
        assert b"SQLite" in file.read()


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_get_engine_encrypted(tmp_path: Path, rand_str: str) -> None:
    key = rand_str.encode()
    enc, _ = encryption.Encryption.create(key)

    # Absolute file
    path = (tmp_path / "absolute.db").absolute()
    e = sql.get_engine(path, enc)
    s = orm.Session(e)
    assert "child" in ORMBase.metadata.tables
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()
    with path.open("rb") as file:
        assert b"SQLite" not in file.read()


def test_escape_not_reserved() -> None:
    assert sql.escape("abc") == "abc"


def test_escape_reserved() -> None:
    assert sql.escape("where") == "`where`"
