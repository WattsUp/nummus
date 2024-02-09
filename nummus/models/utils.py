"""Common API Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy
from rapidfuzz import process
from sqlalchemy import orm

from nummus import utils
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.base import YIELD_PER
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:
    from nummus.models.base import Base

_SEARCH_PROPERTIES: dict[type[Base], list[str]] = {
    Account: ["name", "institution"],
    Asset: ["name", "description", "unit", "tag"],
    TransactionSplit: ["payee", "description", "tag"],
}


def search(
    query: orm.Query[Base],
    cls: type[Base],
    search_str: str | None,
) -> orm.Query[Base]:
    """Perform a fuzzy search and return matches.

    Args:
        query: Session query to execute before fuzzy searching
        cls: Model type to search
        search_str: String to search

    Returns:
        List of results, count of amount results
    """
    # TODO (WattsUp): Caching and cache invalidation
    if search_str is None or len(search_str) < utils.MIN_STR_LEN:
        return query

    # Only fetch the searchable properties to be must faster
    entities: list[orm.InstrumentedAttribute] = [cls.id_]
    entities.extend(getattr(cls, prop) for prop in _SEARCH_PROPERTIES[cls])
    query_unfiltered = query.with_entities(*entities)

    strings: dict[int, str] = {}
    for item in query_unfiltered.yield_per(YIELD_PER):
        item_id = item[0]
        item_str = " ".join(s for s in item[1:] if s is not None)
        strings[item_id] = item_str

    extracted = process.extract(
        search_str,
        strings,
        limit=None,
        processor=lambda s: s.lower(),
    )
    matching_ids: list[int] = [
        i for _, score, i in extracted if score > utils.SEARCH_THRESHOLD
    ]
    if len(matching_ids) == 0:
        # Include poor matches to return something
        matching_ids: list[int] = [i for _, _, i in extracted[:5]]

    return query.session.query(cls).where(cls.id_.in_(matching_ids))


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
        sqlalchemy.func.count(col_one),
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
