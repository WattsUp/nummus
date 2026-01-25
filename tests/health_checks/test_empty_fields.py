from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.empty_fields import EmptyFields
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.asset import Asset
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = EmptyFields()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    c = EmptyFields()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_no_account_number(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        account.number = None
    c = EmptyFields()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == f"{account.uri}.number"
    uri = i.uri

    target = f"Account {account.name} has an empty number"
    assert c.issues == {uri: target}


def test_no_asset_description(
    session: orm.Session,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        asset.description = None
    c = EmptyFields()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == f"{asset.uri}.description"
    uri = i.uri

    target = f"Asset {asset.name} has an empty description"
    assert c.issues == {uri: target}


def test_no_txn_payee(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        txn = transactions[0]
        txn.payee = None
    c = EmptyFields()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == f"{txn.uri}.payee"
    uri = i.uri

    target = f"{txn.date} - {account.name} has an empty payee"
    assert c.issues == {uri: target}


def test_uncategorized(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        t_split = transactions[0].splits[0]
        t_split.category_id = TransactionCategory.uncategorized()[0]
    c = EmptyFields()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == f"{t_split.uri}.category"
    uri = i.uri

    target = f"{t_split.date} - {account.name} is uncategorized"
    assert c.issues == {uri: target}
