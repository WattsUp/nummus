from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

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
    c._commit_issues(session, d)  # noqa: SLF001

    return [(i.value, i.id_) for i in session.query(HealthCheckIssue).all()]


def test_init_properties() -> None:
    c = MockCheck()
    assert c.name == "Mock Check"
    assert c.description == MockCheck._DESC  # noqa: SLF001
    assert not c.any_issues
    assert c.is_severe


def test_any_issues(rand_str: str) -> None:
    c = MockCheck()
    d = {"0": rand_str}
    c._issues = d  # noqa: SLF001
    assert c.any_issues
    assert c.issues == d


def test_commit_issues(session: orm.Session, issues: list[tuple[str, int]]) -> None:
    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.id_ == issues[0][1])
        .one()
    )
    assert i.check == MockCheck.name
    assert i.value is not None
    assert i.msg == "msg 0"
    assert not i.ignore

    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.id_ == issues[1][1])
        .one()
    )
    assert i.check == MockCheck.name
    assert i.value is not None
    assert i.msg == "msg 1"
    assert not i.ignore


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
    assert i.check == MockCheck.name
    assert i.value is not None
    assert i.msg == "msg 0"
    assert i.ignore

    i = (
        session.query(HealthCheckIssue)
        .where(HealthCheckIssue.id_ == issues[1][1])
        .one()
    )
    assert i.check == MockCheck.name
    assert i.value is not None
    assert i.msg == "msg 1"
    assert not i.ignore


@pytest.mark.parametrize("check", CHECKS)
def test_descriptions(check: type[Base]) -> None:
    assert check.description[-1] == "."
