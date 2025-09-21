"""SQL interface."""

from __future__ import annotations

import base64
import sys
from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.event

if TYPE_CHECKING:
    import sqlite3
    from pathlib import Path

    from nummus.encryption import EncryptionInterface

try:
    import sqlcipher3
except ImportError:
    sqlcipher3 = None


_ENGINE_ARGS: dict[str, object] = {}


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, "connect")
def set_sqlite_pragma(db_connection: sqlite3.Connection, *_) -> None:
    """Set PRAGMA upon opening SQLite connection.

    Args:
        db_connection: Connection to SQLite DB

    """
    cursor = db_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # Suppress logging from sqlcipher
    cursor.execute("PRAGMA cipher_log_source=NONE")
    cursor.close()


def get_engine(
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
        db_path = (
            f"sqlite:///{path}"
            if sys.platform == "win32" or not path.is_absolute()
            else f"sqlite:////{path}"
        )
        engine = sqlalchemy.create_engine(db_path, **_ENGINE_ARGS)
    return engine


def escape(s: str) -> str:
    """Escape a string if it is reserved.

    Args:
        s: String to escape

    Returns:
        `s` if escaping is needed else s

    """
    return f"`{s}`" if s in sqlalchemy.sql.compiler.RESERVED_WORDS else s
