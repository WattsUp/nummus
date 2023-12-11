"""Common API Controller."""
from __future__ import annotations

import datetime
import mimetypes
from typing import TYPE_CHECKING

from werkzeug import exceptions

if TYPE_CHECKING:
    import flask
    from sqlalchemy import orm

    from nummus.models import Base

MAX_IMAGE_SIZE = int(1e6)


def find(s: orm.Session, cls: type[Base], uri: str) -> Base:
    """Find the matching object by URI.

    Args:
        s: SQL session to search
        cls: Type of object to find
        uri: URI to find

    Returns:
        Object

    Raises:
        HTTPError(400) if URI is malformed
        HTTPError(404) if object is not found
    """
    try:
        id_ = cls.uri_to_id(uri)
    except TypeError as e:
        raise exceptions.BadRequest(str(e)) from e
    obj = s.query(cls).where(cls.id_ == id_).scalar()
    if obj is None:
        msg = f"{cls.__name__} {uri} not found in Portfolio"
        raise exceptions.NotFound(msg)
    return obj


def parse_period(
    period: str,
    start_custom: datetime.date | None,
    end_custom: datetime.date | None,
) -> tuple[datetime.date | None, datetime.date]:
    """Parse time period from arguments.

    Args:
        period: Name of period
        start_custom: Start date for "custom"
        end_custom: End date from "custom"

    Returns:
        start, end dates
        start is None for "all"
    """
    today = datetime.date.today()
    if period == "custom":
        earliest = datetime.date(1970, 1, 1)
        start = start_custom or today
        end = end_custom or today
        start = max(start, earliest)
        end = max(start, end, earliest)
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
        msg = f"Unknown period: {period}"
        raise exceptions.BadRequest(msg)
    return start, end


def validate_image_upload(req: flask.Request) -> str:
    """Checks image upload meets criteria for accepting.

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
        raise exceptions.LengthRequired

    if req.content_type is None:
        msg = "Request missing Content-Type"
        raise exceptions.UnprocessableEntity(msg)

    if not req.content_type.startswith("image/"):
        msg = f"Content-type must be image/*: {req.content_type}"
        raise exceptions.UnsupportedMediaType(msg)

    suffix = mimetypes.guess_extension(req.content_type)
    if suffix is None:
        msg = f"Unsupported image type: {req.content_type}"
        raise exceptions.UnsupportedMediaType(msg)

    if req.content_length > MAX_IMAGE_SIZE:
        msg = f"Payload length > {MAX_IMAGE_SIZE}B: {req.content_length}B"
        raise exceptions.RequestEntityTooLarge(msg)

    return suffix
