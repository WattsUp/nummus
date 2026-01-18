from __future__ import annotations

from decimal import Decimal

import pytest

from nummus.models.currency import Currency, CURRENCY_FORMATS


@pytest.mark.parametrize("c", [*Currency])
def test_pretty(c: Currency) -> None:
    assert c.pretty


def test_order() -> None:
    assert [*Currency] == sorted(Currency, key=lambda x: x.name)


@pytest.mark.parametrize("c", [*Currency])
def test_format_available(c: Currency) -> None:
    assert CURRENCY_FORMATS.get(c)


@pytest.mark.parametrize(
    ("c", "x", "plus", "coarse", "target"),
    [
        (Currency.CAD, Decimal("1000.1"), False, False, "C$1,000.10"),
        (Currency.CHF, Decimal("1000.1"), False, False, "CHF 1'000.10"),
        (Currency.DKK, Decimal("1000.1"), False, False, "1.000,10 kr"),
        (Currency.EUR, Decimal("1000.1"), False, False, "€1.000,10"),
        (Currency.GBP, Decimal("1000.1"), False, False, "£1,000.10"),
        (Currency.USD, Decimal("1000.1"), False, False, "$1,000.10"),
        (Currency.JPY, Decimal("1000.1"), False, False, "¥1,000"),
        (Currency.USD, Decimal("1000.1"), True, False, "+$1,000.10"),
        (Currency.EUR, Decimal("1000.1"), True, False, "+€1.000,10"),
        (Currency.USD, Decimal("-1000.1"), False, False, "-$1,000.10"),
        (Currency.EUR, Decimal("-1000.1"), False, False, "-€1.000,10"),
        (Currency.CHF, Decimal("-1000.1"), False, False, "CHF -1'000.10"),
        (Currency.USD, Decimal("1000.1"), False, True, "$1,000"),
        (Currency.JPY, Decimal("1234.1"), False, True, "¥1,000"),
        (Currency.USD, Decimal(), False, False, "$0.00"),
    ],
)
def test_format(c: Currency, x: Decimal, plus: bool, coarse: bool, target: str) -> None:
    assert CURRENCY_FORMATS[c](x, plus=plus, coarse=coarse) == target
