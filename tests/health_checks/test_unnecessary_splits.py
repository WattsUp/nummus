from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.health_checks.unnecessary_slits import UnnecessarySplits
from nummus.models import (
    HealthCheckIssue,
    query_count,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Account,
        Transaction,
    )


def test_empty(session: orm.Session) -> None:
    c = UnnecessarySplits()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = UnnecessarySplits()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_check(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    t_split = txn.splits[0]
    t_split = TransactionSplit(
        parent=txn,
        amount=t_split.amount,
        category_id=t_split.category_id,
    )
    session.add(t_split)
    session.commit()

    c = UnnecessarySplits()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == f"{txn.id_}.{t_split.payee}.{t_split.category_id}"
    uri = i.uri

    target = f"{t_split.date} - {account.name}: {t_split.payee or ''} - Other Income"
    assert c.issues == {uri: target}
