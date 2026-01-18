"""Currency definitions."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import NamedTuple, override

from nummus.models.base import BaseEnum


class Currency(BaseEnum):
    """Currency enumeration."""

    CAD = 124
    CHF = 756
    DKK = 208
    EUR = 978
    GBP = 826
    HKD = 344
    JPY = 392
    USD = 840

    @property
    @override
    def pretty(self) -> str:
        return {
            Currency.CAD: "CAD (Canadian Dollar)",
            Currency.CHF: "CHF (Swiss Franc)",
            Currency.DKK: "DKK (Danish Krone)",
            Currency.EUR: "EUR (Euro)",
            Currency.GBP: "GBP (British Pound)",
            Currency.HKD: "HKD (Hong Kong Dollar)",
            Currency.JPY: "JPY (Japanese Yen)",
            Currency.USD: "USD (US Dollar)",
        }[self]


class CurrencyFormat(NamedTuple):
    """Currency format."""

    symbol: str
    sep_1k: str = ","
    sep_dec: str = "."
    symbol_is_suffix: bool = False
    plus_is_prefix: bool = True
    precision: int = 2
    precision_coarse: int = 0

    def __call__(self, x: Decimal, *, plus: bool = False, coarse: bool = False) -> str:
        """Format a number according to the Currency.

        Args:
            x: Number to format
            plus: True will print a + for positive amounts
            coarse: True will round to a larger precision

        Returns:
            x similar to:
               $1,000.00
              -$1,000.00
              C$1,000.00
               €1.000,00
            CHF 1'000.00
                1.000,00 kr
               ¥1,000

        """
        s = ""
        if not self.plus_is_prefix and not self.symbol_is_suffix:
            s += self.symbol

        if x < 0:
            s += "-"
            x = -x
        elif plus:
            s += "+"

        if self.plus_is_prefix and not self.symbol_is_suffix:
            s += self.symbol

        p = self.precision_coarse if coarse else self.precision
        exp = Decimal(10) ** p

        x = round(x * exp) / exp

        v = f"{x:,.{max(0, p)}f}"
        s += re.sub(
            r"[,.]",
            lambda m: self.sep_1k if m.group(0) == "," else self.sep_dec,
            v,
        )

        if self.symbol_is_suffix:
            s += self.symbol

        return s


DEFAULT_CURRENCY = Currency.USD

CURRENCY_FORMATS: dict[Currency, CurrencyFormat] = {
    Currency.CAD: CurrencyFormat("C$"),
    Currency.CHF: CurrencyFormat("CHF ", sep_1k="'", plus_is_prefix=False),
    Currency.DKK: CurrencyFormat(" kr", sep_1k=".", sep_dec=",", symbol_is_suffix=True),
    Currency.EUR: CurrencyFormat("€", sep_1k=".", sep_dec=","),
    Currency.GBP: CurrencyFormat("£"),
    Currency.HKD: CurrencyFormat("HK$"),
    Currency.JPY: CurrencyFormat("¥", precision=0, precision_coarse=-3),
    Currency.USD: CurrencyFormat("$"),
}
