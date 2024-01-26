"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nummus.models import HealthCheckIssue, YIELD_PER

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus import portfolio


class Base(ABC):
    """Base health check class."""

    _NAME: str = ""
    _DESC: str = ""
    _SEVERE: bool = False

    def __init__(self, *_, no_ignores: bool = False) -> None:
        """Initialize Base health check.

        Args:
            no_ignores: True will print issues that have been ignored
        """
        super().__init__()
        # Dictionary of {unique identifier: issue}
        self._issues_raw: t.DictStr = {}
        self._issues: t.DictStr = {}
        self._no_ignores = no_ignores

    @property
    def name(self) -> str:
        """Health check name."""
        return self._NAME

    @property
    def description(self) -> str:
        """Health check description."""
        return self._DESC

    @property
    def issues(self) -> t.DictStr:
        """List of issues this check found."""
        return self._issues

    @property
    def any_issues(self) -> bool:
        """True if check found any issues."""
        return len(self._issues) != 0

    @property
    def is_severe(self) -> bool:
        """True if issues are severe."""
        return self._SEVERE

    @abstractmethod
    def test(self, p: portfolio.Portfolio) -> None:
        """Run the health check on a portfolio.

        Args:
            p: Portfolio to test
        """
        raise NotImplementedError

    @classmethod
    def ignore(cls, p: portfolio.Portfolio, values: list[str] | set[str]) -> None:
        """Ignore false positive issues.

        Args:
            p: Portfolio to test
            values: List of issues to ignore
        """
        with p.get_session() as s:
            query = s.query(HealthCheckIssue.value).where(
                HealthCheckIssue.check == cls._NAME,
                HealthCheckIssue.value.in_(values),
                HealthCheckIssue.ignore.is_(True),
            )
            duplicates = [row[0] for row in query.yield_per(YIELD_PER)]
            values = [v for v in values if v not in duplicates]
            for v in values:
                c = HealthCheckIssue(check=cls._NAME, value=v, ignore=True)
                s.add(c)
            s.commit()

    def get_ignores(self, p: portfolio.Portfolio) -> list[str]:
        """Get list of ignores for this check.

        Args:
            p: Portfolio to test

        Returns:
            List of ignores, interpretation depends on specific check
        """
        if self._no_ignores:
            return []
        with p.get_session() as s:
            query = s.query(HealthCheckIssue.value).where(
                HealthCheckIssue.check == self._NAME,
                HealthCheckIssue.ignore.is_(True),
            )
            return [row[0] for row in query.yield_per(YIELD_PER)]

    def commit_issues(self, p: portfolio.Portfolio) -> None:
        """Commit issues to Portfolio.

        Args:
            p: Portfolio to test
        """
        with p.get_session() as s:
            issues: list[tuple[HealthCheckIssue, str]] = []
            for uri, issue in self._issues_raw.items():
                i = HealthCheckIssue(check=self._NAME, value=uri, ignore=False)
                s.add(i)
                issues.append((i, issue))

            s.commit()
            self._issues = {i.uri: issue for i, issue in issues}
