"""SQL interface
"""

from typing import Dict

import os
import sys

import autodict
import hashlib
import sqlite3
import sqlalchemy
import sqlalchemy.event
from sqlalchemy import pool, orm

try:
  # TODO (WattsUp) figure out Windows sqlcipher installation
  import sqlcipher3  # pylint: disable=import-outside-toplevel
  from nummus.encryption import Encryption  # pylint: disable=import-outside-toplevel
except ImportError:
  # Helpful information printed in nummus.portfolio
  Encryption = None

_SESSIONS: Dict[str, orm.Session] = {}


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
  if path not in _SESSIONS:
    _SESSIONS[path] = orm.Session(bind=_get_engine(path, config, enc))

  return _SESSIONS[path]


def drop_session(path: str = None) -> None:
  """Close database session

  Args:
    path: Path to database file, None will drop all sessions
  """
  if path is None:
    for p in _SESSIONS.values():
      p.close()
    _SESSIONS.clear()
    orm.close_all_sessions()  # Close any danglers
  else:
    if path in _SESSIONS:
      _SESSIONS[path].close()
      _SESSIONS.pop(path)


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
                                      poolclass=pool.NullPool)
  else:
    if sys.platform == "win32":
      db_path = f"sqlite:///{path}"
    else:
      if os.path.isabs(path):
        db_path = f"sqlite:////{path}"
      else:
        db_path = f"sqlite:///{path}"
    engine = sqlalchemy.create_engine(db_path, poolclass=pool.NullPool)
  return engine
