from __future__ import annotations

from typing import override, TYPE_CHECKING

import pytest

from nummus.health_checks import CHECKS
from nummus.health_checks.base import Base
from nummus.models import HealthCheckIssue, query_count

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator


class MockCheck(Base):
    _DESC = "Mock testing health check"
    _SEVERE = True

    @override
    def test(self, s: orm.Session) -> None:
        self._commit_issues(s, {})


@pytest.fixture
def issues(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> list[tuple[str, int]]:
    value_0 = rand_str_generator()
    value_1 = rand_str_generator()
    c = MockCheck()
    d = {value_0: "msg 0", value_1: "msg 1"}
    c._commit_issues(session, d)
    c.ignore(session, [value_0])

    return [(i.value, i.id_) for i in session.query(HealthCheckIssue).all()]


def test_init_properties() -> None:
    c = MockCheck()
    assert c.name() == "Mock check"
    assert c.description() == MockCheck._DESC
    assert not c.any_issues
    assert c.is_severe()


def test_any_issues(rand_str: str) -> None:
    c = MockCheck()
    d = {"0": rand_str}
    c._issues = d
    assert c.any_issues
    assert c.issues == d


@pytest.mark.parametrize("no_ignores", [False, True])
def test_commit_issues(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
    no_ignores: bool,
) -> None:
    value_0 = rand_str_generator()
    value_1 = rand_str_generator()
    c = MockCheck(no_ignores=no_ignores)
    d = {value_0: "msg 0", value_1: "msg 1"}
    c._commit_issues(session, d)
    c.ignore(session, [value_0])
    # Refresh c.issues
    c._commit_issues(session, d)

    i_0 = session.query(HealthCheckIssue).where(HealthCheckIssue.value == value_0).one()
    assert i_0.check == MockCheck.name()
    assert i_0.msg == "msg 0"
    assert i_0.ignore

    i_1 = session.query(HealthCheckIssue).where(HealthCheckIssue.value == value_1).one()
    assert i_1.check == MockCheck.name()
    assert i_1.msg == "msg 1"
    assert not i_1.ignore

    target = {
        i_1.uri: i_1.msg,
    }
    if no_ignores:
        target[i_0.uri] = i_0.msg
    assert c.issues == target


def test_ignore_empty(session: orm.Session, rand_str: str) -> None:
    MockCheck.ignore(session, {rand_str})
    assert query_count(session.query(HealthCheckIssue)) == 0


def test_ignore(
    session: orm.Session,
    issues: list[tuple[str, int]],
) -> None:
    MockCheck.ignore(session, [issues[0][0]])
    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.id_ == issues[0][1])
        .one()
    )
    assert i.check == MockCheck.name()
    assert i.value == issues[0][0]
    assert i.msg == "msg 0"
    assert i.ignore

    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.id_ == issues[1][1])
        .one()
    )
    assert i.check == MockCheck.name()
    assert i.value == issues[1][0]
    assert i.msg == "msg 1"
    assert not i.ignore


@pytest.mark.parametrize("check", CHECKS)
def test_descriptions(check: type[Base]) -> None:
    assert check.description()[-1] == "."
