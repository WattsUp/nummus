from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.health_checks.empty_fields import EmptyFields
from nummus.models import (
    HealthCheckIssue,
    query_count,
    TransactionCategory,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Account,
        Asset,
        Transaction,
    )


def test_empty(session: orm.Session) -> None:
    c = EmptyFields()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = EmptyFields()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_no_account_number(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    account.number = None
    session.commit()
    _ = transactions
    c = EmptyFields()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
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
    asset.description = None
    session.commit()
    _ = transactions
    c = EmptyFields()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
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
    txn = transactions[0]
    txn.payee = None
    session.commit()
    c = EmptyFields()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
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
    t_split = transactions[0].splits[0]
    t_split.category_id = TransactionCategory.uncategorized(session)[0]
    session.commit()
    c = EmptyFields()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == f"{t_split.uri}.category"
    uri = i.uri

    target = f"{t_split.date} - {account.name} is uncategorized"
    assert c.issues == {uri: target}
