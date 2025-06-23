from __future__ import annotations

from pathlib import Path

from sqlalchemy import orm
from typing_extensions import override

from nummus import encryption, sql
from tests.base import TestBase


class ORMBase(orm.DeclarativeBase):
    @orm.declared_attr  # type: ignore[attr-defined]
    @override
    def __tablename__(self) -> str:
        return self.__name__.lower()

    id_: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    def __repr__(self) -> str:
        try:
            return f"<{self.__class__.__name__} id={self.id_}>"
        except orm.exc.DetachedInstanceError:
            return f"<{self.__class__.__name__} id=Detached Instance>"


class Child(ORMBase):
    pass


class TestSQL(TestBase):
    def test_get_engine_unencrypted(self) -> None:
        # Relative file
        path = self._TEST_ROOT.joinpath("unencrypted.db").relative_to(
            Path.cwd(),
        )
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        e = sql.get_engine(path)
        s = orm.Session(e)

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        c = Child()
        s.add(c)
        s.commit()

        with path.open("rb") as file:
            data = file.read()
            self.assertIn(b"SQLite", data)

        self._clean_test_root()

        # Absolute file
        path = self._TEST_ROOT.joinpath("unencrypted.db").absolute()
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        e = sql.get_engine(path)
        s = orm.Session(e)

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        with path.open("rb") as file:
            data = file.read()
            self.assertIn(b"SQLite", data)

    def test_get_engine_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")
        key = self.random_string().encode()
        enc, _ = encryption.Encryption.create(key)

        # Relative file
        path = self._TEST_ROOT.joinpath("encrypted.db").relative_to(Path.cwd())
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        e = sql.get_engine(path, enc)
        s = orm.Session(e)

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        with path.open("rb") as file:
            data = file.read()
            self.assertNotIn(b"SQLite", data)

        self._clean_test_root()

        # Absolute file
        path = self._TEST_ROOT.joinpath("encrypted.db").absolute()
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        e = sql.get_engine(path, enc)
        s = orm.Session(e)

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        with path.open("rb") as file:
            data = file.read()
            self.assertNotIn(b"SQLite", data)

    def test_escape(self) -> None:
        result = sql.escape("abc")
        self.assertEqual(result, "abc")

        result = sql.escape("where")
        self.assertEqual(result, "`where`")
