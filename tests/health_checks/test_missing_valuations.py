from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.health_checks.missing_valuations import MissingAssetValuations
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
    c = MissingAssetValuations()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    txn = transactions[1]
    asset_valuation.date_ord = txn.date_ord
    session.commit()
    c = MissingAssetValuations()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_no_valuations(
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = MissingAssetValuations()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == asset.uri
    uri = i.uri

    target = f"{asset.name} has no valuations"
    assert c.issues == {uri: target}


def test_no_valuations_before_txn(
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    txn = transactions[1]
    c = MissingAssetValuations()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == asset.uri
    uri = i.uri

    target = (
        f"{asset.name} has first transaction on {txn.date} "
        f"before first valuation on {asset_valuation.date}"
    )
    assert c.issues == {uri: target}
