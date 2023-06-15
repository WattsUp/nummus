"""Test module nummus.sql
"""

import uuid

import autodict
import sqlalchemy
from sqlalchemy import orm, schema

from nummus import sql

from tests import base


class ORMBase(orm.DeclarativeBase):
  """Test ORM Base
  
  Attributes:
    id: Unique identifier
  """
  metadata: schema.MetaData

  @orm.declared_attr
  def __tablename__(self):
    return self.__name__.lower()

  id = orm.mapped_column(sqlalchemy.String(36),
                         primary_key=True,
                         default=lambda: str(uuid.uuid4()))

  def __repr__(self) -> str:
    try:
      return f"<{self.__class__.__name__} id={self.id}>"
    except orm.exc.DetachedInstanceError:
      return f"<{self.__class__.__name__} id=Detached Instance>"


class Child(ORMBase):
  """Test derived class of ORMBase
  """
  pass


class TestSQL(base.TestBase):
  """Test SQL methods
  """

  def setUp(self):
    orm.close_all_sessions()
    super().setUp()

  def tearDown(self):
    orm.close_all_sessions()
    super().tearDown()

  def test_get_session_unencrypted(self):
    config = autodict.AutoDict(encrypt=False)

    path = ":memory:"
    s = sql.get_session(path, config)
    self.assertIsNotNone(s)
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    self.assertIn("child", ORMBase.metadata.tables)
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()

    s2 = sql.get_session(path, config)
    self.assertEqual(s, s2)

    s = None
    s2 = None
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    sql.drop_session(path)
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access

    # Relative file
    path = self._TEST_ROOT.joinpath("unencrypted.db")
    self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
    s = sql.get_session(path, config)
    self.assertIsNotNone(s)
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    self.assertIn("child", ORMBase.metadata.tables)
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()

    s = None
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    sql.drop_session(path)
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access
    # Able to call drop after it has been dropped
    sql.drop_session(path)
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access

    with open(path, "rb") as file:
      data = file.read()
      self.assertIn("SQLite".encode(), data)

    self._clean_test_root()

    # Absolute file
    path = self._TEST_ROOT.joinpath("unencrypted.db").absolute()
    self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
    s = sql.get_session(path, config)
    self.assertIsNotNone(s)
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    self.assertIn("child", ORMBase.metadata.tables)
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()

    s = None
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    sql.drop_session()
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access

    with open(path, "rb") as file:
      data = file.read()
      self.assertIn("SQLite".encode(), data)

    self._clean_test_root()

  def test_get_session_encrypted(self):
    if sql.Encryption is None:
      self.skipTest("Encryption is not installed")
    salt = self.random_string()
    key = self.random_string().encode()
    config = autodict.AutoDict(encrypt=True, salt=salt)
    enc = sql.Encryption(key)

    path = ":memory:"
    self.assertRaises(ValueError, sql.get_session, path, config)

    s = sql.get_session(path, config, enc)
    self.assertIsNotNone(s)
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    self.assertIn("child", ORMBase.metadata.tables)
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()

    s = None
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    sql.drop_session(path)
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access

    # Relative file
    path = self._TEST_ROOT.joinpath("encrypted.db")
    self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
    s = sql.get_session(path, config, enc)
    self.assertIsNotNone(s)
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    self.assertIn("child", ORMBase.metadata.tables)
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()

    s = None
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    sql.drop_session(path)
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access

    with open(path, "rb") as file:
      data = file.read()
      self.assertNotIn("SQLite".encode(), data)

    self._clean_test_root()

    # Absolute file
    path = self._TEST_ROOT.joinpath("encrypted.db").absolute()
    self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
    s = sql.get_session(path, config, enc)
    self.assertIsNotNone(s)
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    self.assertIn("child", ORMBase.metadata.tables)
    ORMBase.metadata.create_all(s.get_bind())
    s.commit()

    s = None
    self.assertEqual(len(sql._SESSIONS), 1)  # pylint: disable=protected-access

    sql.drop_session(path)
    self.assertEqual(len(sql._SESSIONS), 0)  # pylint: disable=protected-access

    with open(path, "rb") as file:
      data = file.read()
      self.assertNotIn("SQLite".encode(), data)

    self._clean_test_root()
