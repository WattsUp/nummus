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

    def __init__(self, p: portfolio.Portfolio, *_, no_ignores: bool = False) -> None:
        """Initialize Base health check.

        Args:
            p: Portfolio to test
            no_ignores: True will print issues that have been ignored
        """
        super().__init__()
        # Dictionary of {unique identifier: issue}
        self._issues_raw: t.DictStr = {}
        self._issues: t.DictStr = {}
        self._no_ignores = no_ignores
        self._p = p

        # Remove any unignored issues
        with p.get_session() as s:
            s.query(HealthCheckIssue).where(
                HealthCheckIssue.ignore.is_(False),
                HealthCheckIssue.check == self._NAME,
            ).delete()
            s.commit()

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
    def test(self) -> None:
        """Run the health check on a portfolio."""
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

    def _commit_issues(self) -> None:
        """Commit issues to Portfolio."""
        with self._p.get_session() as s:
            query = s.query(HealthCheckIssue).where(
                HealthCheckIssue.check == self._NAME,
                HealthCheckIssue.ignore.is_(True),
            )
            ignores = {i.value: i for i in query.yield_per(YIELD_PER)}

            issues: list[tuple[HealthCheckIssue, str]] = []
            for value, issue in self._issues_raw.items():
                i = ignores.pop(value, None)
                if i is None:
                    # Not ignored
                    i = HealthCheckIssue(check=self._NAME, value=value, ignore=False)
                    s.add(i)
                    issues.append((i, issue))
                elif self._no_ignores:
                    # No ignores, add the issue to the list
                    issues.append((i, issue))

            # Any leftover ignores are no longer needed, delete them
            for i in ignores.values():
                s.delete(i)

            s.commit()
            self._issues = {i.uri: issue for i, issue in issues}
