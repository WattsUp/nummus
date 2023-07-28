"""Common API Controller
"""

import datetime
import mimetypes
import uuid

from connexion.exceptions import ProblemException as HTTPError
import flask
import sqlalchemy
from sqlalchemy import orm
from thefuzz import process

from nummus import custom_types as t
from nummus.models import (Account, Asset, Base, BaseEnum, Budget, Transaction,
                           TransactionSplit)

_SEARCH_PROPERTIES: t.Dict[t.Type[Base], t.Strings] = {
    Account: ["name", "institution"],
    Asset: ["name", "description", "unit", "tag"],
    TransactionSplit: ["payee", "description", "subcategory", "tag"]
}


def find_account(s: orm.Session, query: str) -> Account:
  """Find the matching Account by UUID

  Args:
    s: SQL session to search
    query: Account UUID to find, will clean first

  Returns:
    Account

  Raises:
    HTTPError(400) if UUID is malformed
    HTTPError(404) if Account is not found
  """
  # Clean
  account_uuid = str(parse_uuid(query))
  acct = s.query(Account).where(Account.uuid == account_uuid).first()
  if acct is None:
    raise HTTPError(404,
                    detail=f"Account {account_uuid} not found in Portfolio")
  return acct


def find_asset(s: orm.Session, query: str) -> Asset:
  """Find the matching Asset by UUID

  Args:
    s: SQL session to search
    query: Asset UUID to find, will clean first

  Returns:
    Asset

  Raises:
    HTTPError(400) if UUID is malformed
    HTTPError(404) if Asset is not found
  """
  # Clean
  asset_uuid = str(parse_uuid(query))
  a = s.query(Asset).where(Asset.uuid == asset_uuid).first()
  if a is None:
    raise HTTPError(404, detail=f"Asset {asset_uuid} not found in Portfolio")
  return a


def find_budget(s: orm.Session, query: str) -> Budget:
  """Find the matching Budget by UUID

  Args:
    s: SQL session to search
    query: Budget UUID to find, will clean first

  Returns:
    Budget

  Raises:
    HTTPError(400) if UUID is malformed
    HTTPError(404) if Budget is not found
  """
  # Clean
  asset_uuid = str(parse_uuid(query))
  b = s.query(Budget).where(Budget.uuid == asset_uuid).first()
  if b is None:
    raise HTTPError(404, detail=f"Budget {asset_uuid} not found in Portfolio")
  return b


def find_transaction(s: orm.Session, query: str) -> Transaction:
  """Find the matching Transaction by UUID

  Args:
    s: SQL session to search
    query: Transaction UUID to find, will clean first

  Returns:
    Transaction

  Raises:
    HTTPError(400) if UUID is malformed
    HTTPError(404) if Transaction is not found
  """
  # Clean
  transaction_uuid = str(parse_uuid(query))
  txn = s.query(Transaction).where(Transaction.uuid == transaction_uuid).first()
  if txn is None:
    raise HTTPError(404,
                    detail=f"Transaction{transaction_uuid} not "
                    "found in Portfolio")
  return txn


def parse_uuid(s: str) -> uuid.UUID:
  """Parse a string to UUID

  Args:
    s: String to parse

  Returns:
    Parsed UUID

  Raises:
    HTTPError(400) if UUID is malformed
  """
  if isinstance(s, uuid.UUID) or s is None:
    return s
  try:
    return uuid.UUID(s)
  except ValueError as e:
    raise HTTPError(400, detail=f"Badly formed UUID: {s}, {e}") from e


def parse_date(s: str) -> datetime.date:
  """Parse a string in ISO format to date

  Args:
    s: String to parse

  Returns:
    Parsed date

  Raises:
    HTTPError(400) if date is malformed
  """
  if isinstance(s, datetime.date) or s is None:
    return s
  try:
    return datetime.date.fromisoformat(s)
  except ValueError as e:
    raise HTTPError(400, detail=f"Badly formed date: {s}, {e}") from e


def parse_enum(s: str, cls: t.Type[BaseEnum]) -> BaseEnum:
  """Parse a string in an enum

  Args:
    s: String to parse

  Returns:
    Parsed enum

  Raises:
    HTTPError(400) if enum is unknown
  """
  if isinstance(s, cls) or s is None:
    return s
  try:
    return cls.parse(s)
  except ValueError as e:
    raise HTTPError(400, detail=f"Unknown {cls.__name__}: {s}, {e}") from e


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
  matching_ids: t.Ints = [i for _, score, i in extracted if score > 70]
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


def validate_image_upload(req: flask.Request) -> str:
  """Checks image upload meets criteria for accepting

  Args:
    req: Request to validate

  Returns:
    Suffix of image based on content-type

  Raises:
    HTTPError(411): Missing Content-Length
    HTTPError(413): Length > 1MB
    HTTPError(415): Unsupported image type
    HTTPError(422): Missing Content-Type
  """
  if req.content_length is None:
    raise HTTPError(411, detail="Request missing Content-Length")

  if req.content_type is None:
    raise HTTPError(422, detail="Request missing Content-Type")

  if not req.content_type.startswith("image/"):
    raise HTTPError(415,
                    detail=f"Content-type must be image/*: {req.content_type}")

  suffix = mimetypes.guess_extension(req.content_type)
  if suffix is None:
    raise HTTPError(415, detail=f"Unsupported image type: {req.content_type}")

  if req.content_length > 1e6:
    raise HTTPError(413, detail=f"Payload length > 1MB: {req.content_length}B")

  return suffix
