"""Common API Controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy
from rapidfuzz import process
from sqlalchemy import orm

from nummus import utils
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus.models.base import Base

_SEARCH_PROPERTIES: t.Dict[t.Type[Base], t.Strings] = {
    Account: ["name", "institution"],
    Asset: ["name", "description", "unit", "tag"],
    TransactionSplit: ["payee", "description", "tag"],
}


def search(
    query: orm.Query[Base],
    cls: t.Type[Base],
    search_str: str,
) -> orm.Query[Base]:
    """Perform a fuzzy search and return matches.

    Args:
        query: Session query to execute before fuzzy searching
        cls: Model type to search
        search_str: String to search

    Returns:
        List of results, count of amount results
    """
    # TODO(WattsUp): Caching and cache invalidation
    if search_str is None or len(search_str) < utils.MIN_STR_LEN:
        return query

    # Only fetch the searchable properties to be must faster
    entities: t.List[orm.InstrumentedAttribute] = [cls.id_]
    for prop in _SEARCH_PROPERTIES[cls]:
        entities.append(getattr(cls, prop))
    query_unfiltered = query.with_entities(*entities)

    unfiltered = query_unfiltered.all()
    strings: t.DictIntStr = {}
    for item in unfiltered:
        item_id = item[0]
        item_str = " ".join(s for s in item[1:] if s is not None)
        strings[item_id] = item_str

    extracted = process.extract(
        search_str,
        strings,
        limit=None,
        processor=lambda s: s.lower(),
    )
    matching_ids: t.Ints = [
        i for _, score, i in extracted if score > utils.SEARCH_THRESHOLD
    ]
    if len(matching_ids) == 0:
        # Include poor matches to return something
        matching_ids: t.Ints = [i for _, _, i in extracted[:5]]

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
    counter = query.statement.with_only_columns(
        sqlalchemy.func.count(col_one),
        maintain_column_froms=True,
    )
    counter = counter.order_by(None)
    return query.session.execute(counter).scalar()


def paginate(
    query: orm.Query[Base],
    limit: int,
    offset: int,
) -> t.Tuple[t.List[Base], int, int]:
    """Paginate query response for smaller results.

    Args:
        query: Session query to execute to get results
        limit: Maximum number of results per page
        offset: Result offset, advances to subsequent pages

    Returns:
        Page (list of result from query), amount count for query, next_offset for
        subsequent calls
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
