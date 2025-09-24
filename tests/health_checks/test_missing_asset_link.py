from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from nummus import utils
from nummus.health_checks.missing_asset_link import MissingAssetLink
from nummus.models import HealthCheckIssue, query_count

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, Asset, Transaction


def test_empty(session: orm.Session) -> None:
    c = MissingAssetLink()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = MissingAssetLink()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_missing_link(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    t_split = transactions[-1].splits[0]
    t_split.asset_id = None
    t_split.asset_quantity_unadjusted = None
    session.commit()
    _ = transactions
    c = MissingAssetLink()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    target = (
        f"{t_split.date} - {account.name}: {utils.format_financial(t_split.amount)} "
        "Securities Traded does not have an asset"
    )
    assert c.issues == {uri: target}


def test_extra_link(
    session: orm.Session,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    t_split = transactions[0].splits[0]
    t_split.asset_id = asset.id_
    t_split.asset_quantity_unadjusted = Decimal()
    session.commit()
    _ = transactions
    c = MissingAssetLink()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    target = (
        f"{t_split.date} - {account.name}: {utils.format_financial(t_split.amount)} "
        "Other Income has an asset"
    )
    assert c.issues == {uri: target}
