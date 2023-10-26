from __future__ import annotations

from pathlib import Path

import autodict
from sqlalchemy import orm, schema

from nummus import sql
from tests.base import TestBase


class ORMBase(orm.DeclarativeBase):
    metadata: schema.MetaData

    @orm.declared_attr
    def __tablename__(self) -> None:
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
    def test_get_session_unencrypted(self) -> None:
        config = autodict.AutoDict(encrypt=False)

        path = None
        self.assertRaises(ValueError, sql.get_session, path, config)

        # Relative file
        path = self._TEST_ROOT.joinpath("unencrypted.db").relative_to(
            Path.cwd(),
        )
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        s = sql.get_session(path, config)
        self.assertIsNotNone(s)
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        s2 = sql.get_session(path, config)
        self.assertNotEqual(s2, s)  # Different sessions
        self.assertEqual(s2.get_bind(), s.get_bind())  # But same engine

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        c = Child()
        s.add(c)
        s.commit()

        s = None
        s2 = None
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        sql.drop_session(path)
        self.assertEqual(len(sql._ENGINES), 0)  # noqa: SLF001
        # Able to call drop after it has been dropped
        sql.drop_session(path)
        self.assertEqual(len(sql._ENGINES), 0)  # noqa: SLF001

        with path.open("rb") as file:
            data = file.read()
            self.assertIn(b"SQLite", data)

        self._clean_test_root()

        # Absolute file
        path = self._TEST_ROOT.joinpath("unencrypted.db").absolute()
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        s = sql.get_session(path, config)
        self.assertIsNotNone(s)
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        s = None
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        sql.drop_session()
        self.assertEqual(len(sql._ENGINES), 0)  # noqa: SLF001

        with path.open("rb") as file:
            data = file.read()
            self.assertIn(b"SQLite", data)

        self._clean_test_root()

    def test_get_session_encrypted(self) -> None:
        if sql.Encryption is None:
            self.skipTest("Encryption is not installed")
        salt = self.random_string()
        key = self.random_string().encode()
        config = autodict.AutoDict(encrypt=True, salt=salt)
        enc = sql.Encryption(key)

        # Relative file
        path = self._TEST_ROOT.joinpath("encrypted.db").relative_to(Path.cwd())
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        self.assertRaises(
            ValueError,
            sql.get_session,
            path,
            config,
        )  # No Encryption object

        s = sql.get_session(path, config, enc)
        self.assertIsNotNone(s)
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        s = None
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        sql.drop_session(path)
        self.assertEqual(len(sql._ENGINES), 0)  # noqa: SLF001

        with path.open("rb") as file:
            data = file.read()
            self.assertNotIn(b"SQLite", data)

        self._clean_test_root()

        # Absolute file
        path = self._TEST_ROOT.joinpath("encrypted.db").absolute()
        self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
        s = sql.get_session(path, config, enc)
        self.assertIsNotNone(s)
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        self.assertIn("child", ORMBase.metadata.tables)
        ORMBase.metadata.create_all(s.get_bind())
        s.commit()

        s = None
        self.assertEqual(len(sql._ENGINES), 1)  # noqa: SLF001

        sql.drop_session(path)
        self.assertEqual(len(sql._ENGINES), 0)  # noqa: SLF001

        with path.open("rb") as file:
            data = file.read()
            self.assertNotIn(b"SQLite", data)

        self._clean_test_root()
