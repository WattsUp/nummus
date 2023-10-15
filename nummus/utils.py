"""Miscellaneous functions and classes."""
from __future__ import annotations

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

THRESHOLD_YEARS = 12 * 1.5
THRESHOLD_WEEKS = 4 * 2
THRESHOLD_DAYS = 7 * 1.5

MONTHS_IN_YEAR = 12
DAYS_IN_YEAR = 365.25
DAYS_IN_WEEK = 7


def camel_to_snake(s: str) -> str:
    """Transform CamelCase to snake_case."""
    s = _REGEX_CC_SC_0.sub(r"\1_\2", s)  # _ at the start of Words
    return _REGEX_CC_SC_1.sub(r"\1_\2", s).lower()  # _ at then end of Words


def get_input(
    prompt: str = "",
    *,
    secure: bool = False,
    print_key: t.Optional[bool] = None,
) -> str:
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
    prompt: t.Optional[str] = None,
    *,
    default: t.Optional[bool] = False,
) -> bool:
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


def parse_real(s: str) -> t.Real:
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
    if "-" in s:
        return Decimal(clean) * -1
    return Decimal(clean)


def format_financial(x: t.Real) -> str:
    """Format a number to financial notation.

    Args:
        x: Number to format

    Returns:
        x formatted similar to $1,000.00 or -$1,000.00
    """
    if x < 0:
        return f"-${-x:,.2f}"
    return f"${x:,.2f}"


def parse_bool(s: str) -> bool:
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


def format_days(days: int, labels: t.Strings = None) -> str:
    """Format number of days to days, weeks, months, or years.

    Args:
        days: Number of days to format
        labels: Override labels [days, weeks, months, years]

    Returns:
        x d
        x wks
        x mos
        x yrs
    """
    labels = labels or ["days", "wks", "mos", "yrs"]
    years = days / DAYS_IN_YEAR
    months = years * MONTHS_IN_YEAR
    if months > THRESHOLD_YEARS:
        return f"{years:.0f} {labels[3]}"
    weeks = days / DAYS_IN_WEEK
    if weeks > THRESHOLD_WEEKS:
        return f"{months:.0f} {labels[2]}"
    if days > THRESHOLD_DAYS:
        return f"{weeks:.0f} {labels[1]}"
    return f"{days} {labels[0]}"


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
