from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.unnecessary_slits import UnnecessarySplits
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = UnnecessarySplits()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    c = UnnecessarySplits()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_check(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        txn = transactions[0]
        t_split = txn.splits[0]
        t_split = TransactionSplit.create(
            parent=txn,
            amount=t_split.amount,
            category_id=t_split.category_id,
        )

    c = UnnecessarySplits()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == f"{txn.id_}.{t_split.payee}.{t_split.category_id}"
    uri = i.uri

    target = f"{t_split.date} - {account.name}: {t_split.payee or ''} - Other Income"
    assert c.issues == {uri: target}
