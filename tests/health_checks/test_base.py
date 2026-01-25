from __future__ import annotations

from typing import override, TYPE_CHECKING

import pytest

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.health_checks.top import HEALTH_CHECKS
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:

    from tests.conftest import RandomStringGenerator


class MockCheck(HealthCheck):
    _DESC = "Mock testing health check"
    _SEVERE = True

    @override
    def test(self) -> None:
        self._commit_issues({})


@pytest.fixture
def issues(
    rand_str_generator: RandomStringGenerator,
) -> list[tuple[str, int]]:
    value_0 = rand_str_generator()
    value_1 = rand_str_generator()
    c = MockCheck()
    d = {value_0: "msg 0", value_1: "msg 1"}
    c._commit_issues(d)
    c.ignore([value_0])

    return [(i.value, i.id_) for i in HealthCheckIssue.all()]


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
    rand_str_generator: RandomStringGenerator,
    no_ignores: bool,
) -> None:
    value_0 = rand_str_generator()
    value_1 = rand_str_generator()
    c = MockCheck(no_ignores=no_ignores)
    d = {value_0: "msg 0", value_1: "msg 1"}
    c._commit_issues(d)
    c.ignore([value_0])
    # Refresh c.issues
    c._commit_issues(d)

    query = HealthCheckIssue.query().where(HealthCheckIssue.value == value_0)
    i_0 = sql.one(query)
    assert i_0.check == MockCheck.name()
    assert i_0.msg == "msg 0"
    assert i_0.ignore

    query = HealthCheckIssue.query().where(HealthCheckIssue.value == value_1)
    i_1 = sql.one(query)
    assert i_1.check == MockCheck.name()
    assert i_1.msg == "msg 1"
    assert not i_1.ignore

    target = {
        i_1.uri: i_1.msg,
    }
    if no_ignores:
        target[i_0.uri] = i_0.msg
    assert c.issues == target


def test_ignore_empty(rand_str: str) -> None:
    MockCheck.ignore({rand_str})
    assert not sql.any_(HealthCheckIssue.query())


def test_ignore(
    issues: list[tuple[str, int]],
) -> None:
    MockCheck.ignore([issues[0][0]])
    query = HealthCheckIssue.query().where(HealthCheckIssue.id_ == issues[0][1])
    i = sql.one(query)
    assert i.check == MockCheck.name()
    assert i.value == issues[0][0]
    assert i.msg == "msg 0"
    assert i.ignore

    query = HealthCheckIssue.query().where(HealthCheckIssue.id_ == issues[1][1])
    i = sql.one(query)
    assert i.check == MockCheck.name()
    assert i.value == issues[1][0]
    assert i.msg == "msg 1"
    assert not i.ignore


@pytest.mark.parametrize("check", HEALTH_CHECKS)
def test_descriptions(check: type[HealthCheck]) -> None:
    assert check.description()[-1] == "."
