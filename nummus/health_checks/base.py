"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nummus.models import HealthCheckIssue, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio


class Base(ABC):
    """Base health check class."""

    _NAME: str = ""
    _DESC: str = ""
    _SEVERE: bool = False

    def __init__(
        self,
        p: portfolio.Portfolio,
        *,
        no_ignores: bool = False,
        **_,
    ) -> None:
        """Initialize Base health check.

        Args:
            p: Portfolio to test
            no_ignores: True will print issues that have been ignored
            all other arguments ignored
        """
        super().__init__()
        # Dictionary of {unique identifier: issue}
        self._issues_raw: dict[str, str] = {}
        self._issues: dict[str, str] = {}
        self._no_ignores = no_ignores
        self._p = p

    @property
    def name(self) -> str:
        """Health check name."""
        return self._NAME

    @property
    def description(self) -> str:
        """Health check description."""
        return self._DESC

    @property
    def issues(self) -> dict[str, str]:
        """List of issues this check found, dict{uri: msg}."""
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
        with p.begin_session() as s:
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

    def _commit_issues(self) -> None:
        """Commit issues to Portfolio."""
        with self._p.begin_session() as s:
            issues: list[tuple[HealthCheckIssue, str]] = []

            raw = dict(self._issues_raw)
            leftovers: list[HealthCheckIssue] = []
            query = s.query(HealthCheckIssue).where(
                HealthCheckIssue.check == self._NAME,
            )
            for i in query.yield_per(YIELD_PER):
                msg = raw.pop(i.value)
                if msg is None:
                    leftovers.append(i)
                else:
                    issues.append((i, msg))

            for value, msg in raw.items():
                if len(leftovers) == 0:
                    i = HealthCheckIssue(
                        check=self._NAME,
                        value=value,
                        msg=msg,
                        ignore=False,
                    )
                    s.add(i)
                    issues.append((i, msg))
                else:
                    i = leftovers.pop(0)
                    i.value = value
                    i.ignore = False
                    i.msg = msg

            # Remaining need to be deleted
            for i in leftovers:
                s.delete(i)

            s.flush()
            self._issues = {
                i.uri: issue for i, issue in issues if self._no_ignores or not i.ignore
            }
