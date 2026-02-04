from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from nummus.commands.health import Health
from nummus.health_checks.top import HEALTH_CHECKS
from nummus.models.config import Config, ConfigKey
from nummus.models.health_checks import HealthCheckIssue
from nummus.portfolio import Portfolio

if TYPE_CHECKING:

    import pytest

    from nummus.portfolio import Portfolio


def test_issues(
    capsys: pytest.CaptureFixture[str],
    empty_portfolio: Portfolio,
    utc_frozen: datetime.datetime,
) -> None:
    c = Health(
        empty_portfolio.path,
        None,
        limit=10,
        ignores=None,
        always_descriptions=True,
        no_ignores=False,
        clear_ignores=False,
        no_description_typos=False,
    )
    assert c.run() != 0

    captured = capsys.readouterr()
    # big output, use "" in checks
    assert "Check 'Database integrity'" in captured.out
    assert "Checks for issues in the underlying" in captured.out
    assert "Check 'Unused categories'" in captured.out
    assert "Has the following issues:" in captured.out
    assert "has no transactions nor budget assignments" in captured.out
    assert "more issues, use --limit flag to see more" in captured.out
    assert "Use web interface to fix issues" in captured.out
    assert not captured.err

    with empty_portfolio.begin_session():
        v = Config.fetch(ConfigKey.LAST_HEALTH_CHECK_TS)
        assert v == utc_frozen.isoformat()


def test_no_limit_severe(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio: Portfolio,
    utc_frozen: datetime.datetime,
) -> None:
    monkeypatch.setattr(
        "nummus.health_checks.unused_categories.UnusedCategories._SEVERE",
        True,
    )
    c = Health(
        empty_portfolio.path,
        None,
        limit=1000,
        ignores=None,
        always_descriptions=True,
        no_ignores=False,
        clear_ignores=False,
        no_description_typos=False,
    )
    assert c.run() != 0

    captured = capsys.readouterr()
    # big output, use "" in checks
    assert "Check 'Database integrity'" in captured.out
    assert "Checks for issues in the underlying" in captured.out
    assert "Check 'Unused categories'" in captured.out
    assert "Has the following issues:" in captured.out
    assert "has no transactions nor budget assignments" in captured.out
    assert "more issues, use --limit flag to see more" not in captured.out
    assert "Use web interface to fix issues" in captured.out
    assert not captured.err

    with empty_portfolio.begin_session():
        v = Config.fetch(ConfigKey.LAST_HEALTH_CHECK_TS)
        assert v == utc_frozen.isoformat()


def test_ignore_all(
    capsys: pytest.CaptureFixture[str],
    empty_portfolio: Portfolio,
    utc_frozen: datetime.datetime,
) -> None:
    ignores: list[str] = []
    for check_type in HEALTH_CHECKS:
        c = check_type()
        with empty_portfolio.begin_session():
            c.test()
        ignores.extend(c.issues.keys())
    with empty_portfolio.begin_session():
        Config.set_(
            ConfigKey.LAST_HEALTH_CHECK_TS,
            (utc_frozen - datetime.timedelta(days=1)).isoformat(),
        )

    c = Health(
        empty_portfolio.path,
        None,
        limit=10,
        ignores=ignores,
        always_descriptions=False,
        no_ignores=False,
        clear_ignores=False,
        no_description_typos=False,
    )
    assert c.run() == 0

    captured = capsys.readouterr()
    # big output, use "" in checks
    assert "Check 'Database integrity'" in captured.out
    assert "Checks for issues in the underlying" not in captured.out
    assert "Has the following issues:" not in captured.out
    assert "has no transactions nor budget assignments" not in captured.out
    assert "more issues, use --limit flag to see more" not in captured.out
    assert "Use web interface to fix issues" not in captured.out
    assert not captured.err

    with empty_portfolio.begin_session():
        v = Config.fetch(ConfigKey.LAST_HEALTH_CHECK_TS)
        assert v == utc_frozen.isoformat()

        assert HealthCheckIssue.count() == len(ignores)


def test_clear_ignores(
    capsys: pytest.CaptureFixture[str],
    empty_portfolio: Portfolio,
) -> None:
    ignores: list[str] = []
    for check_type in HEALTH_CHECKS:
        c = check_type()
        with empty_portfolio.begin_session():
            c.test()
        ignores.extend(c.issues.keys())

    c = Health(
        empty_portfolio.path,
        None,
        limit=10,
        ignores=ignores,
        always_descriptions=False,
        no_ignores=False,
        clear_ignores=True,
        no_description_typos=False,
    )
    assert c.run() != 0

    captured = capsys.readouterr()
    # big output, use "" in checks
    assert "Check 'Unused categories'" in captured.out
    assert "Has the following issues:" in captured.out
    assert "has no transactions nor budget assignments" in captured.out
    assert not captured.err

    with empty_portfolio.begin_session():
        assert HealthCheckIssue.count() == len(ignores)
