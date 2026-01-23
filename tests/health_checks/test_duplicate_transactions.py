from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.duplicate_transactions import DuplicateTransactions
from nummus.models.currency import (
    CURRENCY_FORMATS,
    DEFAULT_CURRENCY,
)
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.transaction import Transaction, TransactionSplit

if TYPE_CHECKING:

    from sqlalchemy import orm


def test_empty() -> None:
    c = DuplicateTransactions()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = DuplicateTransactions()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_duplicate(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions

    txn_to_copy = transactions[0]

    # Fund account on 3 days before today
    with session.begin_nested():
        txn = Transaction.create(
            account_id=txn_to_copy.account_id,
            date=txn_to_copy.date,
            amount=txn_to_copy.amount,
            statement=txn_to_copy.statement,
        )
        TransactionSplit.create(
            parent=txn,
            amount=txn.amount,
            category_id=txn_to_copy.splits[0].category_id,
        )

    c = DuplicateTransactions()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    amount_raw = Transaction.amount.type.process_bind_param(txn.amount, None)
    assert i.value == f"{txn.account_id}.{txn.date_ord}.{amount_raw}"
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    target = f"{txn.date} - Monkey bank checking: {cf(txn.amount)}"
    assert c.issues == {uri: target}
