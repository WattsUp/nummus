from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.health_checks.typos import Typos
from nummus.models import HealthCheckIssue, query_count

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, Asset, Transaction


def test_empty(session: orm.Session) -> None:
    c = Typos()
    c.test(session)
    assert c.issues == {}


def test_no_issues(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    c = Typos()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_mispelled_proper_noun(
    session: orm.Session,
    account: Account,
    account_savings: Account,
) -> None:
    # institution is proper noun so make a almost the same
    account.institution = account_savings.institution + "a"
    session.commit()
    c = Typos()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
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
    # asset description is checked for dictionary spelling
    asset.description = "Banana mispel & 1234 bananas"
    session.commit()
    c = Typos(no_description_typos=no_description_typos)
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == "mispel"
    uri = i.uri

    target = f"Asset {asset.name} description: mispel"
    if no_description_typos:
        assert c.issues == {}
    else:
        assert c.issues == {uri: target}
