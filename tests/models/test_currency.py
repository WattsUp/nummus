from __future__ import annotations

from decimal import Decimal

import pytest

from nummus.models import currency
from nummus.models.currency import Currency


@pytest.mark.parametrize("c", [*Currency])
def test_pretty(c: Currency) -> None:
    assert c.pretty


def test_order() -> None:
    assert [*Currency] == sorted(Currency, key=lambda x: x.name)


@pytest.mark.parametrize("c", [*Currency])
def test_format_available(c: Currency) -> None:
    assert currency.FORMATS.get(c)


@pytest.mark.parametrize(
    ("c", "x", "plus", "target"),
    [
        (Currency.CAD, Decimal("1000.1"), False, "C$1,000.10"),
        (Currency.CHF, Decimal("1000.1"), False, "CHF 1'000.10"),
        (Currency.DKK, Decimal("1000.1"), False, "1.000,10 kr"),
        (Currency.EUR, Decimal("1000.1"), False, "€1.000,10"),
        (Currency.GBP, Decimal("1000.1"), False, "£1,000.10"),
        (Currency.USD, Decimal("1000.1"), False, "$1,000.10"),
        (Currency.YEN, Decimal("1000.1"), False, "¥1,000"),
        (Currency.USD, Decimal("1000.1"), True, "+$1,000.10"),
        (Currency.EUR, Decimal("1000.1"), True, "+€1.000,10"),
        (Currency.USD, Decimal("-1000.1"), False, "-$1,000.10"),
        (Currency.EUR, Decimal("-1000.1"), False, "-€1.000,10"),
        (Currency.USD, Decimal(), False, "$0.00"),
    ],
)
def test_format(c: Currency, x: Decimal, plus: bool, target: str) -> None:
    assert currency.FORMATS[c](x, plus=plus) == target
