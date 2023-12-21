"""Miscellaneous functions and classes."""
from __future__ import annotations

import calendar
import datetime
import getpass
import re
import sys
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nummus import custom_types as t

_REGEX_CC_SC_0 = re.compile(r"(.)([A-Z][a-z]+)")
_REGEX_CC_SC_1 = re.compile(r"([a-z0-9])([A-Z])")

_REGEX_REAL_CLEAN = re.compile(r"[^0-9\.]")

MIN_STR_LEN = 3
SEARCH_THRESHOLD = 60

THRESHOLD_MONTHS = 12 * 1.5
THRESHOLD_WEEKS = 4 * 2
THRESHOLD_DAYS = 7 * 1.5

MONTHS_IN_YEAR = 12
DAYS_IN_YEAR = 365.25
DAYS_IN_WEEK = 7

DAYS_IN_QUARTER = int(DAYS_IN_YEAR // 4)

THRESHOLD_HOURS = 96
THRESHOLD_MINUTES = 90
THRESHOLD_SECONDS = 90

SECONDS_IN_MINUTE = 60
SECONDS_IN_HOUR = 60 * SECONDS_IN_MINUTE
SECONDS_IN_DAY = 24 * SECONDS_IN_HOUR


def camel_to_snake(s: str) -> str:
    """Transform CamelCase to snake_case."""
    s = _REGEX_CC_SC_0.sub(r"\1_\2", s)  # _ at the start of Words
    return _REGEX_CC_SC_1.sub(r"\1_\2", s).lower()  # _ at then end of Words


def get_input(
    prompt: str = "",
    *,
    secure: bool = False,
    print_key: bool | None = None,
) -> str | None:
    """Get input from the user, optionally secure.

    Args:
        prompt: string to print to user
        secure: True will prompt for a password
        print_key: True will print key symbol, False will not, None will check
            stdout.encoding

    Returns:
        str String entered by user, None if canceled
    """
    try:
        if secure:
            if print_key or (
                sys.stdout.encoding and sys.stdout.encoding.lower().startswith("utf-")
            ):
                input_ = getpass.getpass("\u26BF  " + prompt)
            else:
                input_ = getpass.getpass(prompt)
        else:
            input_ = input(prompt)
    except (KeyboardInterrupt, EOFError):
        return None
    return input_


def confirm(
    prompt: str | None = None,
    *,
    default: bool | None = False,
) -> bool | None:
    """Prompt user for yes/no confirmation.

    Args:
        prompt: string to print to user
        default: default response if only [Enter] is pressed

    Returns:
        bool True for yes, False for no
    """
    if prompt is None:
        prompt = "Confirm"

    if default:
        prompt += " [Y/n]: "
    else:
        prompt += " [y/N]: "

    while True:
        input_ = input(prompt)
        if not input_:
            return default
        if input_ in ["Y", "y"]:
            return True
        if input_ in ["N", "n"]:
            return False
        print()
        print("Please enter y or n.")
        print()


def parse_real(s: str | None) -> t.Real | None:
    """Parse a string into a real number.

    Args:
        s: String to parse

    Returns:
        String as number
    """
    if s is None:
        return None
    clean = _REGEX_REAL_CLEAN.sub("", s)
    if clean == "":
        return None
    # Negative if -x.xx or (x.xx)
    if "-" in s or "(" in s:
        return Decimal(clean) * -1
    return Decimal(clean)


def format_financial(x: t.Real, precision: int = 2) -> str:
    """Format a number to financial notation.

    Args:
        x: Number to format
        precision: Number of decimals

    Returns:
        x formatted similar to $1,000.00 or -$1,000.00
    """
    if x < 0:
        return f"-${-x:,.{precision}f}"
    return f"${x:,.{precision}f}"


def parse_bool(s: str) -> bool | None:
    """Parse a string into a bool.

    Args:
        s: String to parse

    Returns:
        Parsed bool
    """
    if not isinstance(s, str):
        msg = "parse_bool: argument must be string"
        raise TypeError(msg)
    if s == "":
        return None
    return s.lower() in ["true", "t", "1"]


def format_days(days: int, labels: t.Strings | None = None) -> str:
    """Format number of days to days, weeks, months, or years.

    Args:
        days: Number of days to format
        labels: Override labels [days, weeks, months, years]

    Returns:
        x days
        x wks
        x mos
        x yrs
    """
    labels = labels or ["days", "wks", "mos", "yrs"]
    years = days / DAYS_IN_YEAR
    months = years * MONTHS_IN_YEAR
    if months > THRESHOLD_MONTHS:
        return f"{years:.0f} {labels[3]}"
    weeks = days / DAYS_IN_WEEK
    if weeks > THRESHOLD_WEEKS:
        return f"{months:.0f} {labels[2]}"
    if days > THRESHOLD_DAYS:
        return f"{weeks:.0f} {labels[1]}"
    return f"{days} {labels[0]}"


def format_seconds(
    seconds: float,
    labels: t.Strings | None = None,
    labels_days: t.Strings | None = None,
) -> str:
    """Format number of seconds to seconds, minutes, or hours.

    Args:
        seconds: Number of seconds to format
        labels: Override labels [seconds, minutes, hours]
        labels_days: Override day labels, passed to format_days

    Returns:
        x s
        x min
        x hrs
        x days
        x wks
        x mos
        x yrs
    """
    labels = labels or ["s", "min", "hrs"]
    hours = seconds / SECONDS_IN_HOUR
    if hours > THRESHOLD_HOURS:
        days = int(seconds // SECONDS_IN_DAY)
        return format_days(days, labels=labels_days)
    minutes = seconds / SECONDS_IN_MINUTE
    if minutes > THRESHOLD_MINUTES:
        return f"{hours:.1f} {labels[2]}"
    if seconds > THRESHOLD_SECONDS:
        return f"{minutes:.1f} {labels[1]}"
    return f"{seconds:.1f} {labels[0]}"


def range_date(
    start: t.Date | int,
    end: t.Date | int,
    *_,
    include_end: bool = True,
) -> t.Dates:
    """Create a range of dates from start to end.

    Args:
        start: First date
        end: Last date
        include_end: True will include end date in range, False will not

    Returns:
        [start, ..., end] if include_end is True
        [start, ..., end) if include_end is False
    """
    start_ord = start if isinstance(start, int) else start.toordinal()
    end_ord = end if isinstance(end, int) else end.toordinal()
    if include_end:
        end_ord += 1
    return [datetime.date.fromordinal(i) for i in range(start_ord, end_ord)]


def date_add_months(date: datetime.date, months: int) -> datetime.date:
    """Add a number of months to a date.

    Args:
        date: Starting date
        months: Number of months to add, negative okay

    Returns:
        datetime.date(date.year, date.month + months, date.day)
    """
    m_sum = date.month + months - 1
    y = date.year + int(m_sum // 12)
    m = (m_sum % 12) + 1
    # Keep day but max out at end of month
    d = min(date.day, calendar.monthrange(y, m)[1])
    return datetime.date(y, m, d)


def round_list(list_: t.Reals, precision: int = 6) -> t.Reals:
    """Round a list, carrying over error such that sum(list) == sum(round_list).

    Args:
        list_: List to round
        precision: Precision to round list to

    Returns:
        List with rounded elements
    """
    residual = Decimal(0)
    l_rounded: t.Reals = []
    for item in list_:
        v = item + residual
        v_round = round(v, precision)
        residual = v - v_round
        l_rounded.append(v_round)

    return l_rounded


def integrate(deltas: list[t.Real | None]) -> t.Reals:
    """Integrate a list starting.

    Args:
        deltas: Change in values, use None instead of zero for faster speed

    Returns:
        list(values) where
        values[0] = sum(deltas[:1])
        values[1] = sum(deltas[:2])
        ...
        values[n] = sum(deltas[:])
    """
    n = len(deltas)
    current = Decimal(0)
    result = [Decimal(0)] * n

    for i, v in enumerate(deltas):
        if v is not None:
            current += v
        result[i] = current

    return result


def interpolate_step(values: list[tuple[int, t.Real]], n: int) -> t.Reals:
    """Interpolate a list of (index, value)s using a step function.

    Indices can be outside of [0, n)

    Args:
        values: List of (index, value)
        n: Length of output array

    Returns:
        list of interpolated values where result[i] = most recent values <= i
    """
    result = [Decimal(0)] * n
    if len(values) == 0:
        return result

    v_current = Decimal(0)
    values_i = 0
    i_next, v_next = values[values_i]
    for i in range(n):
        # If at a valuation, update current and prep next
        if i >= i_next:
            v_current = v_next
            values_i += 1
            try:
                i_next, v_next = values[values_i]
            except IndexError:
                # End of list, set i_v to n to never change current
                i_next = n
        result[i] = v_current

    return result


def interpolate_linear(values: list[tuple[int, t.Real]], n: int) -> t.Reals:
    """Interpolate a list of (index, value)s using a linear function.

    Indices can be outside of [0, n) to interpolate on the boundary

    Args:
        values: List of (index, value)
        n: Length of output array

    Returns:
        list of interpolated values
    """
    result = [Decimal(0)] * n
    if len(values) == 0:
        return result

    # Starting value
    i_current = 0
    v_current = Decimal(0)
    values_i = 0
    i_next, v_next = values[values_i]

    if i_next < 0:
        i_current = i_next
        v_current = v_next
        values_i += 1
        slope_i = -i_next

        # Compute slope to next
        try:
            i_next, v_next = values[values_i]
            slope = (v_next - v_current) / (i_next - i_current)
        except IndexError:
            # End of list, set i_v to n to never change current
            i_next = n
            slope = 0

    else:
        slope = 0
        slope_i = 0

    for i in range(n):
        # If at a valuation, update current and prep next
        if i >= i_next:
            i_current = i_next
            v_current = v_next
            values_i += 1
            slope_i = 0

            # Compute slope to next
            try:
                i_next, v_next = values[values_i]
                slope = (v_next - v_current) / (i_next - i_current)
            except IndexError:
                # End of list set i_v to n to never change current
                i_next = n
                slope = 0
            slope_i = 0
        result[i] = v_current + slope * slope_i
        slope_i += 1

    return result
