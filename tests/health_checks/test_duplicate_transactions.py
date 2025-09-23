from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import utils
from nummus.health_checks.duplicate_transactions import DuplicateTransactions
from nummus.models import HealthCheckIssue, query_count, Transaction, TransactionSplit

if TYPE_CHECKING:

    from sqlalchemy import orm


def test_empty(session: orm.Session) -> None:
    c = DuplicateTransactions()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = DuplicateTransactions()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_duplicate(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions

    txn_to_copy = transactions[0]

    # Fund account on 3 days before today
    txn = Transaction(
        account_id=txn_to_copy.account_id,
        date=txn_to_copy.date,
        amount=txn_to_copy.amount,
        statement=txn_to_copy.statement,
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=txn_to_copy.splits[0].category_id,
    )
    session.add_all((txn, t_split))
    session.commit()

    c = DuplicateTransactions()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    amount_raw = Transaction.amount.type.process_bind_param(txn.amount, None)
    assert i.value == f"{txn.account_id}.{txn.date_ord}.{amount_raw}"
    uri = i.uri

    target = f"{txn.date} - Monkey bank checking: {utils.format_financial(txn.amount)}"
    assert c.issues == {uri: target}
