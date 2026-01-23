from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.uncleared_transactions import UnclearedTransactions
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = UnclearedTransactions()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    c = UnclearedTransactions()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_check(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        txn = transactions[0]
        txn.cleared = False
        t_split = txn.splits[0]
        t_split.parent = txn

    c = UnclearedTransactions()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    target = (
        f"{t_split.date} - {account.name}: "
        f"{CURRENCY_FORMATS[DEFAULT_CURRENCY](t_split.amount)} to {t_split.payee} "
        "is uncleared"
    )
    assert c.issues == {uri: target}
