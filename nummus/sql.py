"""SQL interface."""

from __future__ import annotations

import base64
import sys
from collections.abc import Sequence
from typing import overload, TYPE_CHECKING

import sqlalchemy
import sqlalchemy.event
from sqlalchemy import func, orm

if TYPE_CHECKING:
    import sqlite3
    from collections.abc import Iterable
    from pathlib import Path

    from nummus.encryption.base import EncryptionInterface

try:
    import sqlcipher3
except ImportError:
    sqlcipher3 = None


_ENGINE_ARGS: dict[str, object] = {}

Column = orm.InstrumentedAttribute[str] | orm.InstrumentedAttribute[str | None]
ColumnClause = sqlalchemy.ColumnElement[bool]


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


def to_dict[K, V](query: orm.query.RowReturningQuery[tuple[K, V]]) -> dict[K, V]:
    """Fetch results from query and return a dict.

    Args:
        query: Query that returns 2 columns

    Returns:
        dict{first column: second column}

    """
    return dict(yield_(query))


def count[T](query: orm.Query[T]) -> int:
    """Count the number of result a query will return.

    Args:
        query: Session query to execute

    Returns:
        Number of instances query will return upon execution

    Raises:
        TypeError: if query.statement is not a Select

    """
    # From here:
    # https://datawookie.dev/blog/2021/01/sqlalchemy-efficient-counting/
    col_one: sqlalchemy.ColumnClause[object] = sqlalchemy.literal_column("1")
    stmt = query.statement
    if not isinstance(stmt, sqlalchemy.Select):
        raise TypeError
    counter = stmt.with_only_columns(
        func.count(col_one),
        maintain_column_froms=True,
    )
    counter = counter.order_by(None)
    return query.session.execute(counter).scalar() or 0


def any_[T](query: orm.Query[T]) -> bool:
    """Check if any rows exists in query.

    Args:
        query: Session query to execute

    Returns:
        True if any results

    """
    return count(query.limit(1)) != 0


# TODO (WattsUp): #0 Replace instances of .scalar with this; better typing
@overload
def one[T](
    query: orm.query.RowReturningQuery[tuple[T]],
) -> T: ...


# TODO (WattsUp): #0 Replace instances of .one with this; better typing
@overload
def one[T](query: orm.Query[T]) -> T: ...


def one[T](query: orm.Query[T]) -> object:
    """Check if any rows exists in query.

    Args:
        query: Session query to execute

    Returns:
        One result

    """
    ret: T | Sequence[T] = query.one()
    if not isinstance(ret, Sequence):
        return ret
    return ret[0]  # type: ignore[attr-defined]


@overload
def scalar[T](
    query: orm.query.RowReturningQuery[tuple[T]],
) -> T | None: ...


@overload
def scalar[T](query: orm.Query[T]) -> T | None: ...


def scalar[T](query: orm.Query[T]) -> object | None:
    """Check if any rows exists in query.

    Args:
        query: Session query to execute

    Returns:
        One result

    """
    return query.scalar()


# TODO (WattsUp): #0 Replace instances of .all with this; better typing
@overload
def yield_[T: tuple[object, ...]](
    query: orm.query.RowReturningQuery[T],
) -> Iterable[T]: ...


@overload
def yield_[T](query: orm.Query[T]) -> Iterable[T]: ...


def yield_[T](query: orm.Query[T]) -> Iterable[object]:
    """Yield a query.

    Args:
        query: Query to yield

    Returns:
        Rows

    """
    # Yield per instead of fetch all is faster
    return query.yield_per(100)
