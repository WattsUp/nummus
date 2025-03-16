"""Common API Controller."""

from __future__ import annotations

import datetime
import json
import re
from decimal import Decimal
from typing import TYPE_CHECKING

from typing_extensions import TypeVar

from nummus import exceptions as exc
from nummus import utils
from nummus.models import Base

if TYPE_CHECKING:
    from sqlalchemy import orm


LIMIT_DOWNSAMPLE = 400  # if n_days > LIMIT_DOWNSAMPLE then plot min/avg/max by month
# else plot normally by days

LIMIT_PLOT_YEARS = 400  # if n_days > LIMIT_PLOT_YEARS then plot by years
LIMIT_PLOT_MONTHS = 100  # if n_days > LIMIT_PLOT_MONTHS then plot by months
# else plot normally by days

LIMIT_TICKS_YEARS = 400  # if n_days > LIMIT_TICKS_YEARS then have ticks on the new year
LIMIT_TICKS_MONTHS = 50  # if n_days > LIMIT_TICKS_MONTHS then have ticks on the 1st
LIMIT_TICKS_WEEKS = 20  # if n_days > LIMIT_TICKS_WEEKS then have ticks on Sunday
# else tick each day

HTTP_CODE_OK = 200
HTTP_CODE_REDIRECT = 302
HTTP_CODE_BAD_REQUEST = 400
HTTP_CODE_FORBIDDEN = 403

PERIOD_OPTIONS = {
    "1m": "1M",
    "6m": "6M",
    "ytd": "YTD",
    "1yr": "1Y",
    "max": "MAX",
}


T = TypeVar("T", bound=Base)


def find(s: orm.Session, cls: type[T], uri: str) -> T:
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


def parse_period(period: str) -> tuple[datetime.date | None, datetime.date]:
    """Parse time period from arguments.

    Args:
        period: Name of period

    Returns:
        start, end dates
        start is None for "all"
    """
    today = datetime.date.today()
    if period == "1yr":
        start = datetime.date(today.year - 1, today.month, today.day)
    elif period == "ytd":
        start = datetime.date(today.year, 1, 1)
    elif period == "max":
        start = None
    elif m := re.match(r"(\d)m", period):
        n = min(0, -int(m.group(1)))
        start = utils.date_add_months(today, n)
    else:
        msg = f"Unknown period '{period}'"
        raise exc.http.BadRequest(msg)

    return start, today


def date_labels(start_ord: int, end_ord: int) -> tuple[list[str], str]:
    """Generate date labels and proper date mode.

    Args:
        start_ord: Start date ordinal
        end_ord: End date ordinal

    Returns:
        tuple(list of labels, date mode)
    """
    dates = utils.range_date(start_ord, end_ord)
    n = len(dates)
    if n > LIMIT_TICKS_YEARS:
        date_mode = "years"
    elif n > LIMIT_TICKS_MONTHS:
        date_mode = "months"
    elif n > LIMIT_TICKS_WEEKS:
        date_mode = "weeks"
    else:
        date_mode = "days"
    return [d.isoformat() for d in dates], date_mode


def ctx_to_json(d: dict[str, object]) -> str:
    """Convert web context to JSON.

    Args:
        d: Object to serialize

    Returns:
        JSON object
    """

    def default(obj: object) -> str | float:
        if isinstance(obj, Decimal):
            return float(round(obj, 2))
        msg = f"Unknown type {type(obj)}"
        raise TypeError(msg)

    return json.dumps(d, default=default, separators=(",", ":"))
