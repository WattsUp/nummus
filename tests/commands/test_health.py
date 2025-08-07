from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from colorama import Fore

from nummus import health_checks
from nummus.commands.health import Health
from nummus.models import Config, ConfigKey, HealthCheckIssue, query_count

if TYPE_CHECKING:

    import pytest

    from nummus.portfolio import Portfolio


def test_issues(
    capsys: pytest.CaptureFixture,
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
    assert f"{Fore.GREEN}Check 'Database integrity'" in captured.out
    assert f"{Fore.CYAN}    Checks for issues in the underlying" in captured.out
    assert f"{Fore.YELLOW}Check 'Unused categories'" in captured.out
    assert f"{Fore.YELLOW}  Has the following issues:" in captured.out
    assert "has no transactions nor budget assignments" in captured.out
    assert "more issues, use --limit flag to see more" in captured.out
    assert f"{Fore.MAGENTA}Use web interface to fix issues" in captured.out
    assert not captured.err

    with empty_portfolio.begin_session() as s:
        c = s.query(Config).where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS).one()
        assert c.value == utc_frozen.isoformat()


def test_no_limit_severe(
    capsys: pytest.CaptureFixture,
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
    assert f"{Fore.GREEN}Check 'Database integrity'" in captured.out
    assert f"{Fore.CYAN}    Checks for issues in the underlying" in captured.out
    assert f"{Fore.RED}Check 'Unused categories'" in captured.out
    assert f"{Fore.RED}  Has the following issues:" in captured.out
    assert "has no transactions nor budget assignments" in captured.out
    assert "more issues, use --limit flag to see more" not in captured.out
    assert f"{Fore.MAGENTA}Use web interface to fix issues" in captured.out
    assert not captured.err

    with empty_portfolio.begin_session() as s:
        c = s.query(Config).where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS).one()
        assert c.value == utc_frozen.isoformat()


def test_ignore_all(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    utc_frozen: datetime.datetime,
) -> None:
    ignores: list[str] = []
    for check_type in health_checks.CHECKS:
        c = check_type()
        with empty_portfolio.begin_session() as s:
            c.test(s)
        ignores.extend(c.issues.keys())
    with empty_portfolio.begin_session() as s:
        c = Config(
            key=ConfigKey.LAST_HEALTH_CHECK_TS,
            value=(utc_frozen - datetime.timedelta(days=1)).isoformat(),
        )
        s.add(c)

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
    assert f"{Fore.GREEN}Check 'Database integrity'" in captured.out
    assert f"{Fore.CYAN}    Checks for issues in the underlying" not in captured.out
    assert f"{Fore.YELLOW}Check 'Unused categories'" not in captured.out
    assert f"{Fore.YELLOW}  Has the following issues:" not in captured.out
    assert "has no transactions nor budget assignments" not in captured.out
    assert "more issues, use --limit flag to see more" not in captured.out
    assert f"{Fore.MAGENTA}Use web interface to fix issues" not in captured.out
    assert not captured.err

    with empty_portfolio.begin_session() as s:
        c = s.query(Config).where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS).one()
        assert c.value == utc_frozen.isoformat()

        assert query_count(s.query(HealthCheckIssue)) == len(ignores)


def test_clear_ignores(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:
    ignores: list[str] = []
    for check_type in health_checks.CHECKS:
        c = check_type()
        with empty_portfolio.begin_session() as s:
            c.test(s)
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
    assert f"{Fore.YELLOW}Check 'Unused categories'" in captured.out
    assert f"{Fore.YELLOW}  Has the following issues:" in captured.out
    assert "has no transactions nor budget assignments" in captured.out
    assert not captured.err

    with empty_portfolio.begin_session() as s:
        assert query_count(s.query(HealthCheckIssue)) == len(ignores)
