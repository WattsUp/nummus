from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import sql
from nummus.health_checks.typos import Typos
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.account import Account
    from nummus.models.asset import Asset
    from nummus.models.transaction import Transaction


def test_empty() -> None:
    c = Typos()
    c.test()
    assert c.issues == {}


def test_no_issues(
    transactions: list[Transaction],
) -> None:
    c = Typos()
    c.test()
    assert not sql.any_(HealthCheckIssue.query())


def test_mispelled_proper_noun(
    session: orm.Session,
    account: Account,
    account_savings: Account,
) -> None:
    with session.begin_nested():
        # institution is proper noun so make a almost the same
        account.institution = account_savings.institution + "a"
    c = Typos()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == account.institution
    uri = i.uri

    target = f"Account {account.name} institution: {account.institution}"
    assert c.issues == {uri: target}


@pytest.mark.parametrize("no_description_typos", [False, True])
def test_mispelled(
    session: orm.Session,
    asset: Asset,
    no_description_typos: bool,
) -> None:
    with session.begin_nested():
        # asset description is checked for dictionary spelling
        asset.description = "Banana mispel & 1234 bananas"
    c = Typos(no_description_typos=no_description_typos)
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == "mispel"
    uri = i.uri

    target = f"Asset {asset.name} description: mispel"
    if no_description_typos:
        assert c.issues == {}
    else:
        assert c.issues == {uri: target}
