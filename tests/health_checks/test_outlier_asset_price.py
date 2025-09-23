from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.health_checks.outlier_asset_price import OutlierAssetPrice
from nummus.models import (
    HealthCheckIssue,
    query_count,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Asset,
        AssetValuation,
        Transaction,
    )


def test_empty(session: orm.Session) -> None:
    c = OutlierAssetPrice()
    c.test(session)
    assert c.issues == {}


def test_zero_quantity(
    session: orm.Session,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    t_split = transactions[1].splits[0]
    t_split.asset_quantity_unadjusted = Decimal()
    asset_valuation.date_ord = t_split.date_ord
    asset_valuation.value = Decimal(10)
    session.commit()

    c = OutlierAssetPrice()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


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
    t_split = transactions[1].splits[0]
    asset_valuation.date_ord = t_split.date_ord
    asset_valuation.value = Decimal(10)
    t_split.amount = amount
    session.commit()

    c = OutlierAssetPrice()
    c.test(session)

    if target_word is None:
        assert query_count(session.query(HealthCheckIssue)) == 0
        return
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    target = (
        f"{t_split.date}: {asset.name} "
        f"was traded at {utils.format_financial(amount / -10)} which is "
        f"{target_word} valuation of {utils.format_financial(asset_valuation.value)}"
    )
    assert c.issues == {uri: target}
