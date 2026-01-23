from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from nummus import sql
from nummus.health_checks.overdrawn_accounts import OverdrawnAccounts
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = OverdrawnAccounts()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    c = OverdrawnAccounts()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_check(
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    with session.begin_nested():
        t_split = transactions[0].splits[0]
        t_split.amount = Decimal(-1)
    c = OverdrawnAccounts()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == f"{account.id_}.{t_split.date_ord}"
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    target = f"{t_split.date} - {account.name}: {cf(t_split.amount)}"
    assert c.issues == {uri: target}
