from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.missing_valuations import MissingAssetValuations
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.asset import (
        Asset,
        AssetValuation,
    )
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = MissingAssetValuations()
    c.test()
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    with session.begin_nested():
        txn = transactions[1]
        asset_valuation.date_ord = txn.date_ord
    c = MissingAssetValuations()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_no_valuations(
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    c = MissingAssetValuations()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == asset.uri
    uri = i.uri

    target = f"{asset.name} has no valuations"
    assert c.issues == {uri: target}


def test_no_valuations_before_txn(
    asset: Asset,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    txn = transactions[1]
    c = MissingAssetValuations()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == asset.uri
    uri = i.uri

    target = (
        f"{asset.name} has first transaction on {txn.date} "
        f"before first valuation on {asset_valuation.date}"
    )
    assert c.issues == {uri: target}
