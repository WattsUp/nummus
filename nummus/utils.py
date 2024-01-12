"""Miscellaneous functions and classes."""

from __future__ import annotations

import calendar
import datetime
import getpass
import re
import shutil
import sys
from decimal import Decimal
from typing import TYPE_CHECKING

from nummus import global_config

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

MATCH_PERCENT = Decimal("0.05")
MATCH_ABSOLUTE = Decimal(10)


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
            secure_icon = global_config.get(global_config.ConfigKey.SECURE_ICON)
            if print_key is True or (
                print_key is None
                and sys.stdout.encoding
                and sys.stdout.encoding.lower().startswith("utf-")
            ):
                input_ = getpass.getpass(f"{secure_icon}  {prompt}")
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


def period_months(start_ord: int, end_ord: int) -> dict[str, tuple[int, int]]:
    """Split a period into months.

    Args:
        start_ord: First date ordinal of period
        end_ord: Last date ordinal of period

    Returns:
        A dictionary of months and the ordinals that start and end them
        dict{"2000-01": (start_ord_0, end_ord_0), "2000-02": ...}
        Results will not fall outside of start_ord and end_ord
    """
    date = datetime.date.fromordinal(start_ord)
    y = date.year
    m = date.month
    end = datetime.date.fromordinal(end_ord)
    end_y = end.year
    end_m = end.month
    months: dict[str, tuple[int, int]] = {}
    while y < end_y or (y == end_y and m <= end_m):
        start_of_month = datetime.date(y, m, 1).toordinal()
        end_of_month = datetime.date(y, m, calendar.monthrange(y, m)[1]).toordinal()
        months[f"{y:04}-{m:02}"] = (
            max(start_ord, start_of_month),
            min(end_ord, end_of_month),
        )
        y = y + (m // 12)
        m = (m % 12) + 1
    return months


def period_years(start_ord: int, end_ord: int) -> dict[str, tuple[int, int]]:
    """Split a period into years.

    Args:
        start_ord: First date ordinal of period
        end_ord: Last date ordinal of period

    Returns:
        A dictionary of years and the ordinals that start and end them
        dict{"2000": (start_ord_0, end_ord_0), "2001": ...}
        Results will not fall outside of start_ord and end_ord
    """
    year = datetime.date.fromordinal(start_ord).year
    end_year = datetime.date.fromordinal(end_ord).year
    years: dict[str, tuple[int, int]] = {}
    while year <= end_year:
        jan_1 = datetime.date(year, 1, 1).toordinal()
        dec_31 = datetime.date(year, 12, 31).toordinal()
        years[str(year)] = (max(start_ord, jan_1), min(end_ord, dec_31))
        year += 1
    return years


def downsample(
    start_ord: int,
    end_ord: int,
    values: t.Reals,
) -> tuple[t.Strings, t.Reals, t.Reals, t.Reals]:
    """Downsample a list of values to min/avg/max by month.

    Args:
        start_ord: First date ordinal of period
        end_ord: Last date ordinal of period
        values: Daily values

    Returns:
        (labels, min, avg, max)
    """
    periods = period_months(start_ord, end_ord)
    labels: t.Strings = []
    values_min: t.Reals = []
    values_avg: t.Reals = []
    values_max: t.Reals = []

    # TODO (WattsUp): Not a very fast algorithm especially when downsampling many
    for period, limits in periods.items():
        values_sliced = values[limits[0] - start_ord : limits[1] - start_ord + 1]
        labels.append(period)
        values_min.append(min(values_sliced))
        values_max.append(max(values_sliced))
        values_avg.append(sum(values_sliced) / len(values_sliced))  # type: ignore[attr-defined]

    return labels, values_min, values_avg, values_max


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


def integrate(deltas: list[t.Real | None] | t.Reals) -> t.Reals:
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


def print_table(table: list[list[str] | None]) -> None:
    """Pretty print tabular data.

    First row is header, able to configure how columns behave
    "<Header" will left align text, default
    ">Header" will right align text
    "^Header" will center align text
    "Header." will prioritize this column for truncation with ellipsis if too long
    "Header/" will prevent this column being truncated

    Args:
        table: List of table rows, None will print a horizontal line
    """
    if len(table) < 1:
        msg = "Table has no rows"
        raise ValueError(msg)
    table = list(table)

    header_raw = table[0]
    if header_raw is None:
        msg = "First row cannot be None"
        raise ValueError(msg)

    col_widths = [0] * len(header_raw)
    table[0] = [c.strip("<>^./") for c in header_raw]
    label_widths = [len(c) for c in table[0]]
    for row in table:
        if row is None:
            continue
        for i, cell in enumerate(row):
            col_widths[i] = max(len(cell), col_widths[i])

    # Adjust col widths if sum is over terminal width
    margin = shutil.get_terminal_size()[0] - sum(col_widths) - len(col_widths) - 2
    excess: t.Ints = []
    for i, cell in enumerate(header_raw):
        n_label = label_widths[i]
        if margin < 0 and cell[-1] == ".":
            n = max(n_label, col_widths[i] + margin)
            n_trim = col_widths[i] - n
            col_widths[i] = n
            margin += n_trim
        excess.append(0 if cell[-1] == "/" else col_widths[i] - n_label)
    while margin < 0 and any(excess):
        for i, e in enumerate(excess):
            if margin < 0 and e > 0:
                col_widths[i] -= 1
                excess[i] -= 1
                margin += 1

    formats = []
    for cell, n in zip(header_raw, col_widths, strict=True):
        align = cell[0]
        align = align if align in "<>^" else ""
        formats.append(f"{align}{n}")

    # Print the box
    print("╭" + "┬".join("─" * n for n in col_widths) + "╮")
    buf = "│".join(f"{c:^{n}}" for c, n in zip(table[0], col_widths, strict=True))
    print("│" + buf + "│")
    for row in table[1:]:
        if row is None:
            print("╞" + "╪".join("═" * n for n in col_widths) + "╡")
        else:
            formatted_row = []
            for i, cell in enumerate(row):
                if len(cell) > col_widths[i]:
                    cell_truncated = cell[: col_widths[i] - 3]
                    formatted_row.append(cell_truncated + "...")
                else:
                    formatted_row.append(f"{cell:{formats[i]}}")
            print("│" + "│".join(formatted_row) + "│")

    print("╰" + "┴".join("─" * n for n in col_widths) + "╯")
