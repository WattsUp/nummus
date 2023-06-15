"""SQL interface
"""

from typing import Dict

import os
import sys

import autodict
import hashlib
import sqlalchemy
from sqlalchemy import pool, orm

try:
  # TODO (WattsUp) figure out Windows sqlcipher installation
  import sqlcipher3  # pylint: disable=import-outside-toplevel
  from nummus.encryption import Encryption  # pylint: disable=import-outside-toplevel
except ImportError:
  # Helpful information printed in nummus.portfolio
  Encryption = None

_SESSIONS: Dict[str, orm.Session] = {}


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
  path = str(path)
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
    path = str(path)
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

  if config["encrypt"]:
    if enc is None:
      raise ValueError("Encryption object must be provided to encrypt engine")
    db_key = hashlib.sha256(enc.key + config["salt"].encode()).hexdigest()
    db_path = "sqlite+pysqlcipher://:" + db_key + "@"
    if path == ":memory:" or not os.path.isabs(path):
      db_path += "/"
    else:
      db_path += "//"
    db_path += path
    engine = sqlalchemy.create_engine(db_path,
                                      module=sqlcipher3,
                                      poolclass=pool.NullPool)
  else:
    if path in ["", ":memory:"]:
      db_path = "sqlite:///:memory:"
    elif sys.platform == "win32":
      db_path = "sqlite:///" + path
    else:
      if os.path.isabs(path):
        db_path = "sqlite:////" + path
      else:
        db_path = "sqlite:///" + path
    engine = sqlalchemy.create_engine(db_path, poolclass=pool.NullPool)
  return engine
