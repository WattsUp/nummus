"""SQL interface
"""

import typing as t

import os
import sys

import autodict
import hashlib
import sqlite3
import sqlalchemy
import sqlalchemy.event
from sqlalchemy import orm

try:
  # TODO (WattsUp) figure out Windows sqlcipher installation
  import sqlcipher3  # pylint: disable=import-outside-toplevel
  from nummus.encryption import Encryption  # pylint: disable=import-outside-toplevel
except ImportError:
  # Helpful information printed in nummus.portfolio
  Encryption = None

# Cache engines so recomputing db_key is avoided
_ENGINES: t.Dict[str, sqlalchemy.engine.Engine] = {}

_ENGINE_ARGS: t.Dict[str, object] = {}


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, "connect")
def set_sqlite_pragma(db_connection: sqlite3.Connection, *_) -> None:
  """Hook to set PRAGMA upon opening SQLite connection

  Args:
    db_connection: Connection to SQLite DB
  """
  cursor = db_connection.cursor()
  cursor.execute("PRAGMA foreign_keys=ON")
  cursor.close()


def get_session(path: str,
                config: autodict.AutoDict,
                enc: Encryption = None) -> orm.Session:
  """Get database session

  Args:
    path: Path to database file
    config: Configuration provider
    enc: Encryption object storing the key

  Returns:
    Session to database
  """
  if path is None:
    raise ValueError("Path must not be None")
  if path not in _ENGINES:
    _ENGINES[path] = _get_engine(path, config, enc)

  return orm.Session(bind=_ENGINES[path])


def drop_session(path: str = None) -> None:
  """Close database session

  Args:
    path: Path to database file, None will drop all sessions
  """
  if path is None:
    orm.close_all_sessions()  # Close any sessions
    _ENGINES.clear()
  else:
    _ENGINES.pop(path, None)


def _get_engine(path: str,
                config: autodict.AutoDict,
                enc: Encryption = None) -> sqlalchemy.engine.Engine:
  """Get sqlalchemy Engine to the database

  Args:
    path: Path to database file
    config: Configuration provider
    enc: Encryption object storing the key

  Returns:
    sqlalchemy.Engine
  """
  # Cannot support in-memory DB cause every transaction closes it
  if config["encrypt"]:
    if enc is None:
      raise ValueError("Encryption object must be provided to encrypt engine")
    db_key = hashlib.sha256(enc.key + config["salt"].encode()).hexdigest()
    if not os.path.isabs(path):
      sep = "/"
    else:
      sep = "//"
    db_path = f"sqlite+pysqlcipher://:{db_key}@{sep}{path}"
    engine = sqlalchemy.create_engine(db_path,
                                      module=sqlcipher3,
                                      **_ENGINE_ARGS)
  else:
    if sys.platform == "win32":
      db_path = f"sqlite:///{path}"
    else:
      if os.path.isabs(path):
        db_path = f"sqlite:////{path}"
      else:
        db_path = f"sqlite:///{path}"
    engine = sqlalchemy.create_engine(db_path, **_ENGINE_ARGS)
  return engine
