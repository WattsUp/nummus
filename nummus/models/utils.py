"""Common API Controller
"""

from rapidfuzz import process
import sqlalchemy
from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models import Account, Asset, Base, TransactionSplit

_SEARCH_PROPERTIES: t.Dict[t.Type[Base], t.Strings] = {
    Account: ["name", "institution"],
    Asset: ["name", "description", "unit", "tag"],
    TransactionSplit: ["payee", "description", "subcategory", "tag"]
}


def search(query: orm.Query[Base], cls: t.Type[Base],
           search_str: str) -> orm.Query[Base]:
  """Perform a fuzzy search and return matches

  Args:
    query: Session query to execute before fuzzy searching
    cls: Model type to search
    search_str: String to search

  Returns:
    List of results, count of total results
  """
  # TODO (WattsUp) Caching and cache invalidation
  if search_str is None or len(search_str) < 3:
    return query

  unfiltered = query.all()
  strings: t.DictIntStr = {}
  for instance in unfiltered:
    parameters: t.Strings = []
    for k in _SEARCH_PROPERTIES[cls]:
      parameters.append(getattr(instance, k))
    i_str = " ".join(p for p in parameters if p is not None)
    strings[instance.id] = i_str

  extracted = process.extract(search_str, strings, limit=None)
  matching_ids: t.Ints = [i for _, score, i in extracted if score > 60]
  if len(matching_ids) == 0:
    # Include poor matches to return something
    matching_ids: t.Ints = [i for _, _, i in extracted[:5]]

  return query.session.query(cls).where(cls.id.in_(matching_ids))


def query_count(query: orm.Query[Base]) -> int:
  """Count the number of result a query will return

  Args:
    query: Session query to execute

  Returns:
    Number of instances query will return upon execution
  """
  # From here:
  # https://datawookie.dev/blog/2021/01/sqlalchemy-efficient-counting/
  col_one = sqlalchemy.literal_column("1")
  counter = query.statement.with_only_columns(
      # It is callable, count returns a generator type
      sqlalchemy.func.count(col_one),  # pylint: disable=not-callable
      maintain_column_froms=True)
  counter = counter.order_by(None)
  return query.session.execute(counter).scalar()


def paginate(query: orm.Query[Base], limit: int,
             offset: int) -> t.Tuple[t.List[Base], int, int]:
  """Paginate query response for smaller results

  Args:
    query: Session query to execute to get results
    limit: Maximum number of results per page
    offset: Result offset, advances to subsequent pages

  Returns:
    Page (list of result from query), total count for query, next_offset for
    subsequent calls
  """
  offset = max(0, offset)

  # Get total number from filters
  count = query_count(query)

  # Apply limiting, and offset
  query = query.limit(limit).offset(offset)

  results = query.all()

  # Compute next_offset
  n_current = len(results)
  remaining = count - n_current - offset
  if remaining > 0:
    next_offset = offset + n_current
  else:
    next_offset = None

  return results, count, next_offset