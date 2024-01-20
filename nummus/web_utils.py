"""Common API Controller."""

from __future__ import annotations

import datetime
import mimetypes
import re
from typing import TYPE_CHECKING

from nummus import exceptions as exc
from nummus import utils

if TYPE_CHECKING:
    import flask
    from sqlalchemy import orm

    from nummus.models import Base

MAX_IMAGE_SIZE = int(1e6)

LIMIT_DOWNSAMPLE = 400  # if n_days > LIMIT_DOWNSAMPLE then plot min/avg/max by month
# else plot normally by days

LIMIT_PLOT_YEARS = 400  # if n_days > LIMIT_PLOT_YEARS then plot by years
LIMIT_PLOT_MONTHS = 100  # if n_days > LIMIT_PLOT_MONTHS then plot by months
# else plot normally by days

LIMIT_TICKS_MONTHS = 50  # if n_days > LIMIT_TICKS_MONTHS then have ticks on the 1st
LIMIT_TICKS_WEEKS = 20  # if n_days > LIMIT_TICKS_WEEKS then have ticks on Sunday
# else tick each day

# if n_days > LIMIT_DEFER then defer response with a spinner
LIMIT_DEFER = 200


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
    except (exc.InvalidURIError, exc.WrongURITypeError) as e:
        raise exc.http.BadRequest(str(e)) from e
    try:
        obj = s.query(cls).where(cls.id_ == id_).one()
    except exc.NoResultFound as e:
        msg = f"{cls.__name__} {uri} not found in Portfolio"
        raise exc.http.NotFound(msg) from e
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
    elif m_days := re.match(r"(\d+)-days", period):
        n = int(m_days.group(1))
        start = today - datetime.timedelta(days=n)
        end = today
    elif m_months := re.match(r"(\d+)-months", period):
        n = int(m_months.group(1))
        start_this_month = datetime.date(today.year, today.month, 1)
        start = utils.date_add_months(start_this_month, -n)
        end = today
    elif m_years := re.match(r"(\d+)-years?", period):
        n = int(m_years.group(1))
        start = datetime.date(today.year - n, today.month, 1)
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
        raise exc.http.BadRequest(msg)
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
        raise exc.http.LengthRequired

    if req.content_type is None:
        msg = "Request missing Content-Type"
        raise exc.http.UnprocessableEntity(msg)

    if not req.content_type.startswith("image/"):
        msg = f"Content-type must be image/*: {req.content_type}"
        raise exc.http.UnsupportedMediaType(msg)

    suffix = mimetypes.guess_extension(req.content_type)
    if suffix is None:
        msg = f"Unsupported image type: {req.content_type}"
        raise exc.http.UnsupportedMediaType(msg)

    if req.content_length > MAX_IMAGE_SIZE:
        msg = f"Payload length > {MAX_IMAGE_SIZE}B: {req.content_length}B"
        raise exc.http.RequestEntityTooLarge(msg)

    return suffix
