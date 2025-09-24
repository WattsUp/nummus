from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import utils
from nummus.health_checks.uncleared_transactions import UnclearedTransactions
from nummus.models import HealthCheckIssue, query_count

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, Transaction


def test_empty(session: orm.Session) -> None:
    c = UnclearedTransactions()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = UnclearedTransactions()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_check(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    txn.cleared = False
    t_split = txn.splits[0]
    t_split.parent = txn
    session.commit()

    c = UnclearedTransactions()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == t_split.uri
    uri = i.uri

    target = (
        f"{t_split.date} - {account.name}: "
        f"{utils.format_financial(t_split.amount)} to {t_split.payee} "
        "is uncleared"
    )
    assert c.issues == {uri: target}
