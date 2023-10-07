"""Common API Controller
"""

import datetime
import mimetypes
import uuid

import flask
from sqlalchemy import orm
from werkzeug import exceptions

from nummus import custom_types as t
from nummus.models import Base, BaseEnum


def find(s: orm.Session,
         cls: t.Type[Base],
         query: str,
         do_raise: bool = True) -> Base:
  """Find the matching object by UUID

  Args:
    s: SQL session to search
    cls: Type of object to find
    query: UUID to find, will clean first
    do_raise: True will raise 404 if not found, False will return None instead

  Returns:
    Object

  Raises:
    HTTPError(400) if UUID is malformed
    HTTPError(404) if object is not found
  """
  # Clean
  u = str(parse_uuid(query))
  obj = s.query(cls).where(cls.uuid == u).first()
  if obj is None and do_raise:
    raise exceptions.NotFound(f"{cls.__name__} {u} not found in Portfolio")
  return obj


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
    raise exceptions.BadRequest(f"Badly formed UUID: {s}, {e}") from e


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
    raise exceptions.BadRequest(f"Badly formed date: {s}, {e}") from e


def parse_enum(s: str, cls: t.Type[BaseEnum]) -> BaseEnum:
  """Parse a string into an enum

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
    raise exceptions.BadRequest(f"Unknown {cls.__name__}: {s}, {e}") from e


def parse_period(period: str, start_custom: str,
                 end_custom: str) -> t.Tuple[datetime.date, datetime.date]:
  """Parse time period from arguments

  Args:
    period: Name of period
    start: Start date for "custom"
    end: End date from "custom"

  Returns:
    start, end dates
    start is None for "all"
  """
  today = datetime.date.today()
  if period == "custom":
    start = parse_date(start_custom)
    end = parse_date(end_custom) or today
    end = max(start, end)
  elif period == "this-month":
    start = datetime.date(today.year, today.month, 1)
    end = today
  elif period == "last-month":
    start_this_month = datetime.date(today.year, today.month, 1)
    end = start_this_month - datetime.timedelta(days=1)
    start = datetime.date(end.year, end.month, 1)
  elif period == "30-days":
    start = today - datetime.timedelta(days=30)
    end = today
  elif period == "90-days":
    start = today - datetime.timedelta(days=90)
    end = today
  elif period == "1-year":
    start = datetime.date(today.year - 1, today.month, 1)
    end = today
  elif period == "5-years":
    start = datetime.date(today.year - 5, today.month, 1)
    end = today
  elif period == "this-year":
    start = datetime.date(today.year, 1, 1)
    end = today
  elif period == "last-year":
    start = datetime.date(today.year - 1, 1, 1)
    end = datetime.date(today.year - 1, 12, 31)
  elif period == "all":
    start = None
    end = today
  else:
    raise exceptions.BadRequest(f"Unknown period: {period}")
  return start, end


def parse_bool(s: str) -> bool:
  """Parse a string into a bool

  Args:
    s: String to parse

  Returns:
    Parsed bool
  """
  if isinstance(s, bool) or s is None:
    return s
  if s == "":
    return None
  return s.lower() in ["true", "t", "1", 1]


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
    raise exceptions.LengthRequired()

  if req.content_type is None:
    raise exceptions.UnprocessableEntity("Request missing Content-Type")

  if not req.content_type.startswith("image/"):
    raise exceptions.UnsupportedMediaType(
        f"Content-type must be image/*: {req.content_type}")

  suffix = mimetypes.guess_extension(req.content_type)
  if suffix is None:
    raise exceptions.UnsupportedMediaType(
        f"Unsupported image type: {req.content_type}")

  if req.content_length > 1e6:
    raise exceptions.RequestEntityTooLarge(
        f"Payload length > 1MB: {req.content_length}B")

  return suffix
