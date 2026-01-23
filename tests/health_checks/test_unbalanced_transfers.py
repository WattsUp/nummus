from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.unbalanced_transfers import UnbalancedTransfers
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = UnbalancedTransfers()
    c.test()
    assert c.issues == {}


def test_no_transfers(
    transactions: list[Transaction],
) -> None:
    c = UnbalancedTransfers()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_no_issues(
    today: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    with session.begin_nested():
        amount = Decimal(100)
        spec = [
            (0, amount),
            (0, -amount),
            (1, amount),
            (1, -amount),
        ]
        for i, (dt, a) in enumerate(spec):
            txn = transactions_spending[i]
            txn.date = today + datetime.timedelta(days=dt)
            t_split = txn.splits[0]
            t_split.category_id = categories["transfers"]
            t_split.amount = a
            t_split.parent = txn

    c = UnbalancedTransfers()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_wrong_amount(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    with session.begin_nested():
        amount = Decimal(100)
        spec = [amount, -amount * 2]
        for i, a in enumerate(spec):
            t_split = transactions_spending[i].splits[0]
            t_split.category_id = categories["transfers"]
            t_split.amount = a

    c = UnbalancedTransfers()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == today.isoformat()
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    lines = (
        f"{today}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {cf(Decimal(100), plus=True):>14} Transfers",
        f"  {account.name}: {cf(Decimal(-200), plus=True):>14} Transfers",
    )
    assert c.issues == {uri: "\n".join(lines)}


def test_one_pair(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    with session.begin_nested():
        amount = Decimal(100)
        spec = [amount, -amount, -amount]
        for i, a in enumerate(spec):
            t_split = transactions_spending[i].splits[0]
            t_split.category_id = categories["transfers"]
            t_split.amount = a

    c = UnbalancedTransfers()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == today.isoformat()
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    lines = (
        f"{today}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {cf(Decimal(-100), plus=True):>14} Transfers",
    )
    assert c.issues == {uri: "\n".join(lines)}


def test_wrong_date(
    today: datetime.date,
    account: Account,
    session: orm.Session,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    with session.begin_nested():
        amount = Decimal(100)
        spec = [
            (0, amount),
            (0, -amount),
            (0, amount),
            (1, -amount),
        ]
        for i, (dt, a) in enumerate(spec):
            txn = transactions_spending[i]
            txn.date = today + datetime.timedelta(days=dt)
            t_split = txn.splits[0]
            t_split.category_id = categories["transfers"]
            t_split.amount = a
            t_split.parent = txn
        amount = Decimal(100)
    tomorrow = today + datetime.timedelta(days=1)

    c = UnbalancedTransfers()
    c.test()
    assert HealthCheckIssue.count() == 2

    i = (
        HealthCheckIssue.query()
        .where(HealthCheckIssue.value == today.isoformat())
        .one()
    )
    assert i.check == c.name()
    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    lines = (
        f"{today}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {cf(Decimal(100), plus=True):>14} Transfers",
    )
    assert i.msg == "\n".join(lines)

    i = (
        HealthCheckIssue.query()
        .where(HealthCheckIssue.value == tomorrow.isoformat())
        .one()
    )
    assert i.check == c.name()
    assert i.value == tomorrow.isoformat()
    lines = (
        f"{tomorrow}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {cf(Decimal(-100), plus=True):>14} Transfers",
    )
    assert i.msg == "\n".join(lines)
