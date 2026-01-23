from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import sql
from nummus.health_checks.outlier_asset_price import OutlierAssetPrice
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.asset import (
        Asset,
        AssetValuation,
    )
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = OutlierAssetPrice()
    c.test()
    assert c.issues == {}


def test_zero_quantity(
    session: orm.Session,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    with session.begin_nested():
        t_split = transactions[1].splits[0]
        t_split.asset_quantity_unadjusted = Decimal()
        asset_valuation.date_ord = t_split.date_ord
        asset_valuation.value = Decimal(10)

    c = OutlierAssetPrice()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


@pytest.mark.parametrize(
    ("amount", "target_word"),
    [
        (Decimal(-100), None),
        (Decimal(-10), "below"),
        (Decimal(-200), "above"),
    ],
)
def test_check(
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
    amount: Decimal,
    target_word: str | None,
) -> None:
    with session.begin_nested():
        t_split = transactions[1].splits[0]
        asset_valuation.date_ord = t_split.date_ord
        asset_valuation.value = Decimal(10)
        t_split.amount = amount

    c = OutlierAssetPrice()
    c.test()

    if target_word is None:
        assert not sql.any_(HealthCheckIssue.query())
        return
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    target = (
        f"{t_split.date}: {asset.name} "
        f"was traded at {cf(amount / -10)} which is "
        f"{target_word} valuation of {cf(asset_valuation.value)}"
    )
    assert c.issues == {uri: target}
