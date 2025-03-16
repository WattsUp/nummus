"""Common API Controller."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import (
    CheckConstraint,
    Constraint,
    ForeignKeyConstraint,
    func,
    orm,
    UniqueConstraint,
)

if TYPE_CHECKING:
    from nummus.models.base import Base


def query_count(query: orm.Query[Base]) -> int:
    """Count the number of result a query will return.

    Args:
        query: Session query to execute

    Returns:
        Number of instances query will return upon execution
    """
    # From here:
    # https://datawookie.dev/blog/2021/01/sqlalchemy-efficient-counting/
    col_one = sqlalchemy.literal_column("1")
    counter = query.statement.with_only_columns(  # type: ignore[attr-defined]
        func.count(col_one),
        maintain_column_froms=True,
    )
    counter = counter.order_by(None)
    return query.session.execute(counter).scalar() or 0


def paginate(
    query: orm.Query[Base],
    limit: int,
    offset: int,
) -> tuple[list[Base], int, int | None]:
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
    count = query_count(query)

    # Apply limiting, and offset
    query = query.limit(limit).offset(offset)

    results = query.all()

    # Compute next_offset
    n_current = len(results)
    remaining = count - n_current - offset
    next_offset = offset + n_current if remaining > 0 else None

    return results, count, next_offset


# Debug only code, no need to test
def dump_table_configs(
    s: orm.Session,
    model: type[Base] | None = None,
) -> list[str]:
    """Get the table configs (columns and constraints) and print.

    Args:
        s: SQL session to use
        model: Filter to specific table

    Returns:
        List of lines used to create tables
    """
    table_filter = f"AND name='{model.__tablename__}'" if model else ""
    stmt = f"""
        SELECT sql
        FROM sqlite_master
        WHERE
            type='table' {table_filter}
        """.strip()  # noqa: S608
    result = s.execute(sqlalchemy.text(stmt)).one()[0]
    result: str
    return [s.replace("\t", "    ") for s in result.splitlines()]


def get_constraints(
    s: orm.Session,
    model: type[Base],
) -> list[tuple[type[Constraint], str]]:
    """Get constraints of a table.

    Args:
        s: SQL session to use
        model: Filter to specific table

    Returns:
        list[(Constraint type, construction text)]
    """
    config = "\n".join(dump_table_configs(s, model))
    constraints: list[tuple[type[Constraint], str]] = []

    re_unique = re.compile(r"UNIQUE \(([^\)]+)\)")
    for cols in re_unique.findall(config):
        cols: str
        constraints.append((UniqueConstraint, cols))

    re_check = re.compile(r'CONSTRAINT "[^"]+" CHECK \(([^\)]+)\)')
    for sql_text in re_check.findall(config):
        sql_text: str
        constraints.append((CheckConstraint, sql_text))

    re_foreign = re.compile(r"FOREIGN KEY\((\w+)\) REFERENCES \w+ \(\w+\)")
    for cols in re_foreign.findall(config):
        sql_text: str
        constraints.append((ForeignKeyConstraint, cols))

    return constraints
