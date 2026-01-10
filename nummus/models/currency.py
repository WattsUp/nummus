"""Currency definitions."""

from __future__ import annotations

from typing import NamedTuple, override, TYPE_CHECKING

from nummus.models.base import BaseEnum

if TYPE_CHECKING:
    from decimal import Decimal


class Currency(BaseEnum):
    """Currency enumeration."""

    CAD = 124
    CHF = 756
    DKK = 208
    EUR = 978
    GBP = 826
    USD = 840
    YEN = 392

    @property
    @override
    def pretty(self) -> str:
        return {
            Currency.CAD: "CAD (Canadian Dollar)",
            Currency.CHF: "CHF (Swiss Franc)",
            Currency.DKK: "DKK (Danish Krone)",
            Currency.EUR: "EUR (Euro)",
            Currency.GBP: "GBP (British Pound)",
            Currency.USD: "USD (US Dollar)",
            Currency.YEN: "YEN (Japanese Yen)",
        }[self]


class Format(NamedTuple):
    """Currency format."""

    symbol: str
    sep_1k: str = ","
    sep_dec: str = "."
    is_suffix: bool = False
    precision: int = 2

    def __call__(self, x: Decimal, *, plus: bool = False) -> str:
        """Format a number according to the Currency.

        Args:
            x: Number to format
            plus: True will print a + for positive amounts

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
        if x < 0:
            s = "-"
            x = -x
        elif plus:
            s = "+"
        else:
            s = ""

        if not self.is_suffix:
            s += self.symbol

        v = f"{x:_.{self.precision}f}"
        s += v.replace(".", self.sep_dec).replace("_", self.sep_1k)

        if self.is_suffix:
            s += self.symbol

        return s


DEFAULT_CURRENCY = Currency.USD

FORMATS: dict[Currency, Format] = {
    Currency.CAD: Format("C$"),
    Currency.CHF: Format("CHF ", sep_1k="'"),
    Currency.DKK: Format(" kr", sep_1k=".", sep_dec=",", is_suffix=True),
    Currency.EUR: Format("€", sep_1k=".", sep_dec=","),
    Currency.GBP: Format("£"),
    Currency.USD: Format("$"),
    Currency.YEN: Format("¥", precision=0),
}
