"""Common API Controller."""

from __future__ import annotations

from collections import defaultdict

import sqlalchemy
from rapidfuzz import process
from sqlalchemy import func, orm
from typing_extensions import TypeVar

from nummus import utils
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.base import Base, YIELD_PER
from nummus.models.transaction import TransactionSplit

_SEARCH_PROPERTIES: dict[type[Base], list[str]] = {
    Account: ["name", "institution"],
    Asset: ["name", "description", "unit", "tag"],
    TransactionSplit: ["payee", "description", "tag"],
}


T = TypeVar("T", bound=Base)


def search(
    query: orm.Query[T],
    cls: type[T],
    search_str: str | None,
) -> orm.Query[T]:
    """Perform a fuzzy search and return matches.

    Args:
        query: Session query to execute before fuzzy searching
        cls: Model type to search
        search_str: String to search

    Returns:
        List of results, count of amount results
    """
    if search_str is None or len(search_str) < utils.MIN_STR_LEN:
        return query

    # Only fetch the searchable properties to be must faster
    entities: list[orm.InstrumentedAttribute] = [cls.id_]
    entities.extend(getattr(cls, prop) for prop in _SEARCH_PROPERTIES[cls])
    query_unfiltered = query.with_entities(*entities)

    strings: dict[str, list[int]] = defaultdict(list)
    for item in query_unfiltered.yield_per(YIELD_PER):
        item_id = item[0]
        item_str = " ".join(s for s in item[1:] if s is not None)
        strings[item_str.lower()].append(item_id)

    extracted = process.extract(
        search_str,
        strings.keys(),
        limit=5,
    )

    matching_ids: list[int] = []
    for item_str, _, _ in extracted:
        matching_ids.extend(strings[item_str])

    return query.where(cls.id_.in_(matching_ids))


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


def dump_table_configs(s: orm.Session, model: type[Base] | None = None) -> None:
    """Get the table configs (columns and constraints) and print.

    Args:
        s: SQL session to use
        model: Filter to specific table
    """
    table_filter = f"AND name='{model.__tablename__}'" if model else ""
    stmt = f"""
        SELECT sql
        FROM sqlite_master
        WHERE
            type='table' {table_filter}
        """.strip()  # noqa: S608
    result = s.execute(sqlalchemy.text(stmt))
    for (row,) in result.yield_per(YIELD_PER):
        row: str
        for line in row.splitlines():
            print(line)
