from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from nummus import utils
from nummus.health_checks.overdrawn_accounts import OverdrawnAccounts
from nummus.models import HealthCheckIssue, query_count

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, Transaction


def test_empty(session: orm.Session) -> None:
    c = OverdrawnAccounts()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    session.commit()
    c = OverdrawnAccounts()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_check(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    t_split = transactions[0].splits[0]
    t_split.amount = Decimal(-1)
    c = OverdrawnAccounts()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == f"{account.id_}.{t_split.date_ord}"
    uri = i.uri

    target = (
        f"{t_split.date} - {account.name}: {utils.format_financial(t_split.amount)}"
    )
    assert c.issues == {uri: target}
