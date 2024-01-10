"""SQL interface."""

from __future__ import annotations

import base64
import sys
from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.event
from sqlalchemy import orm

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from nummus import custom_types as t
    from nummus.encryption import EncryptionInterface

try:
    # TODO(WattsUp): figure out Windows sqlcipher installation
    import sqlcipher3
except ImportError:
    sqlcipher3 = None

# Cache engines so recomputing db_key is avoided
_ENGINES: dict[Path, sqlalchemy.engine.Engine] = {}

_ENGINE_ARGS: t.DictAny = {}


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, "connect")
def set_sqlite_pragma(db_connection: sqlite3.Connection, *_) -> None:
    """Hook to set PRAGMA upon opening SQLite connection.

    Args:
        db_connection: Connection to SQLite DB
    """
    cursor = db_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session(
    path: Path,
    enc: EncryptionInterface | None = None,  # type: ignore[attr-defined]
) -> orm.Session:
    """Get database session.

    Args:
        path: Path to database file
        config: Configuration provider
        enc: Encryption object storing the key

    Returns:
        Session to database
    """
    if path is None:
        msg = "Path must not be None"
        raise ValueError(msg)
    if path not in _ENGINES:
        _ENGINES[path] = _get_engine(path, enc)

    return orm.Session(bind=_ENGINES[path])


def drop_session(path: Path | None = None) -> None:
    """Close database session.

    Args:
        path: Path to database file, None will drop all sessions
    """
    if path is None:
        orm.close_all_sessions()  # Close any sessions
        _ENGINES.clear()
    else:
        _ENGINES.pop(path, None)


def _get_engine(
    path: Path,
    enc: EncryptionInterface | None = None,
) -> sqlalchemy.engine.Engine:
    """Get sqlalchemy Engine to the database.

    Args:
        path: Path to database file
        config: Configuration provider
        enc: Encryption object storing the key

    Returns:
        sqlalchemy.Engine
    """
    # Cannot support in-memory DB cause every transaction closes it
    if enc is not None:
        db_key = base64.urlsafe_b64encode(enc.hashed_key).decode()
        sep = "//" if path.is_absolute() else "/"
        db_path = f"sqlite+pysqlcipher://:{db_key}@{sep}{path}"
        engine = sqlalchemy.create_engine(db_path, module=sqlcipher3, **_ENGINE_ARGS)
    else:
        if sys.platform == "win32" or not path.is_absolute():
            db_path = f"sqlite:///{path}"
        else:
            db_path = f"sqlite:////{path}"
        engine = sqlalchemy.create_engine(db_path, **_ENGINE_ARGS)
    return engine
