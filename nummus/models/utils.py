"""Common API Controller."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    UniqueConstraint,
)

from nummus import sql

if TYPE_CHECKING:
    from sqlalchemy import (
        Constraint,
        orm,
    )

    from nummus.models.base import Base


def paginate[T: Base](
    query: orm.Query[T],
    limit: int,
    offset: int,
) -> tuple[list[T], int, int | None]:
    """Paginate query response for smaller results.

    Args:
        query: Session query to execute to get results
        limit: Maximum number of results per page
        offset: Result offset, advances to subsequent pages

    Returns:
        Page (list of result from query), amount count for query, next_offset for
        subsequent calls (None if no more)

    """
    offset = max(0, offset)

    # Get amount number from filters
    count = sql.count(query)

    # Apply limiting, and offset
    query = query.limit(limit).offset(offset)

    results = list(sql.yield_(query))

    # Compute next_offset
    n_current = len(results)
    remaining = count - n_current - offset
    next_offset = offset + n_current if remaining > 0 else None

    return results, count, next_offset


def dump_table_configs(model: type[Base]) -> list[str]:
    """Get the table configs (columns and constraints) and print.

    Args:
        model: Filter to specific table

    Returns:
        List of lines used to create tables

    """
    stmt = f"""
        SELECT sql
        FROM sqlite_master
        WHERE
            type='table'
            AND name='{model.__tablename__}'
        """.strip()  # noqa: S608
    query: orm.query.RowReturningQuery[tuple[str]] = model.session().execute(  # type: ignore[attr-defined]
        sqlalchemy.text(stmt),
    )
    result: str = sql.one(query)
    return [s.replace("\t", "    ") for s in result.splitlines()]


def get_constraints(
    model: type[Base],
) -> list[tuple[type[Constraint], str]]:
    """Get constraints of a table.

    Args:
        model: Filter to specific table

    Returns:
        list[(Constraint type, construction text)]

    """
    config = "\n".join(dump_table_configs(model))

    re_unique = re.compile(r"UNIQUE \(([^\)]+)\)")
    constraints: list[tuple[type[Constraint], str]] = [
        (UniqueConstraint, cols) for cols in re_unique.findall(config)
    ]

    re_check = re.compile(r'CONSTRAINT "[^"]+" CHECK \(([^\)]+)\)')
    constraints.extend(
        (CheckConstraint, sql_text) for sql_text in re_check.findall(config)
    )

    re_foreign = re.compile(r"FOREIGN KEY\((\w+)\) REFERENCES \w+ \(\w+\)")
    constraints.extend(
        (ForeignKeyConstraint, cols) for cols in re_foreign.findall(config)
    )

    return constraints


def update_rows[T: Base](
    cls: type[T],
    query: orm.Query[T],
    id_key: str,
    updates: dict[object, dict[str, object]],
) -> None:
    """Update many rows, reusing leftovers when possible.

    Args:
        cls: Type of model to update
        query: Query to fetch all applicable models
        id_key: Name of property used for identification
        updates: dict{id_value: {parameter: value}}

    """
    updates = updates.copy()
    leftovers: list[Base] = []

    for m in sql.yield_(query):
        update = updates.pop(getattr(m, id_key), None)
        if update is None:
            # No longer needed
            leftovers.append(m)
        else:
            for k, v in update.items():
                setattr(m, k, v)

    s = cls.session()

    # Add any missing ones
    for id_, update in updates.items():
        if leftovers:
            m = leftovers.pop(0)
            setattr(m, id_key, id_)
            for k, v in update.items():
                setattr(m, k, v)
        else:
            cls.create(**{id_key: id_, **update})

    # Delete any leftovers
    for m in leftovers:
        s.delete(m)


def update_rows_list[T: Base](
    cls: type[T],
    query: orm.Query[T],
    updates: list[dict[str, object]],
) -> list[int]:
    """Update many rows, reusing leftovers when possible.

    Args:
        cls: Type of model to update
        query: Query to fetch all applicable models
        updates: list[{parameter: value}]

    Returns:
        list[cls.id_ for each updated/created]

    """
    ids: list[int] = []

    updates = updates.copy()
    leftovers: list[Base] = []

    for m in sql.yield_(query):
        if len(updates) == 0:
            # No longer needed
            leftovers.append(m)
        else:
            update = updates.pop(0)
            for k, v in update.items():
                setattr(m, k, v)
            ids.append(m.id_)

    s = cls.session()

    to_add = [cls(**update) for update in updates]
    s.add_all(to_add)

    # Delete any leftovers
    for m in leftovers:
        s.delete(m)

    s.flush()
    ids.extend(m.id_ for m in to_add)

    return ids
