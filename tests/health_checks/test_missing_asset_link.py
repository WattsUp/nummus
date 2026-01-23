from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from nummus.health_checks.missing_asset_link import MissingAssetLink
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.asset import Asset
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = MissingAssetLink()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = MissingAssetLink()
    c.test()
    assert HealthCheckIssue.count() == 0


def test_missing_link(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        t_split = transactions[-1].splits[0]
        t_split.asset_id = None
        t_split.asset_quantity_unadjusted = None
    c = MissingAssetLink()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    target = (
        f"{t_split.date} - {account.name}: {cf(t_split.amount)} "
        "Securities Traded does not have an asset"
    )
    assert c.issues == {uri: target}


def test_extra_link(
    session: orm.Session,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        t_split = transactions[0].splits[0]
        t_split.asset_id = asset.id_
        t_split.asset_quantity_unadjusted = Decimal()
    c = MissingAssetLink()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    target = (
        f"{t_split.date} - {account.name}: {cf(t_split.amount)} "
        "Other Income has an asset"
    )
    assert c.issues == {uri: target}
