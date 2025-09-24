from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from nummus import utils
from nummus.health_checks.unbalanced_transfers import UnbalancedTransfers
from nummus.models import HealthCheckIssue, query_count

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, Transaction


def test_empty(session: orm.Session) -> None:
    c = UnbalancedTransfers()
    c.test(session)
    assert c.issues == {}


def test_no_transfers(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = UnbalancedTransfers()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_no_issues(
    today: datetime.date,
    session: orm.Session,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
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
    session.commit()

    c = UnbalancedTransfers()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_wrong_amount(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    amount = Decimal(100)
    spec = [amount, -amount * 2]
    for i, a in enumerate(spec):
        t_split = transactions_spending[i].splits[0]
        t_split.category_id = categories["transfers"]
        t_split.amount = a
    session.commit()

    c = UnbalancedTransfers()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == today.isoformat()
    uri = i.uri

    lines = (
        f"{today}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {utils.format_financial(Decimal(-200), plus=True):>14} "
        "Transfers",
        f"  {account.name}: {utils.format_financial(Decimal(100), plus=True):>14} "
        "Transfers",
    )
    assert c.issues == {uri: "\n".join(lines)}


def test_one_pair(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
    amount = Decimal(100)
    spec = [amount, -amount, -amount]
    for i, a in enumerate(spec):
        t_split = transactions_spending[i].splits[0]
        t_split.category_id = categories["transfers"]
        t_split.amount = a
    session.commit()

    c = UnbalancedTransfers()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == today.isoformat()
    uri = i.uri

    lines = (
        f"{today}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {utils.format_financial(Decimal(-100), plus=True):>14} "
        "Transfers",
    )
    assert c.issues == {uri: "\n".join(lines)}


def test_wrong_date(
    today: datetime.date,
    account: Account,
    session: orm.Session,
    transactions_spending: list[Transaction],
    categories: dict[str, int],
) -> None:
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
    session.commit()
    tomorrow = today + datetime.timedelta(days=1)

    c = UnbalancedTransfers()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 2

    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.value == today.isoformat())
        .one()
    )
    assert i.check == c.name()
    lines = (
        f"{today}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {utils.format_financial(Decimal(100), plus=True):>14} "
        "Transfers",
    )
    assert i.msg == "\n".join(lines)

    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.value == tomorrow.isoformat())
        .one()
    )
    assert i.check == c.name()
    assert i.value == tomorrow.isoformat()
    lines = (
        f"{tomorrow}: Sum of transfers on this day are non-zero",
        f"  {account.name}: {utils.format_financial(Decimal(-100), plus=True):>14} "
        "Transfers",
    )
    assert i.msg == "\n".join(lines)
