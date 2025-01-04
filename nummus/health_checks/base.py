"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nummus import utils
from nummus.models import HealthCheckIssue, YIELD_PER
from nummus.utils import classproperty

if TYPE_CHECKING:
    from nummus import portfolio


class Base(ABC):
    """Base health check class."""

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

    @classproperty
    def name(cls) -> str:  # noqa: N805
        """Health check name."""
        return utils.camel_to_snake(cls.__name__).replace("_", " ").title()

    @classproperty
    def description(cls) -> str:  # noqa: N805
        """Health check description."""
        return cls._DESC

    @property
    def issues(self) -> dict[str, str]:
        """List of issues this check found, dict{uri: msg}."""
        return self._issues

    @property
    def any_issues(self) -> bool:
        """True if check found any issues."""
        return len(self._issues) != 0

    @classproperty
    def is_severe(cls) -> bool:  # noqa: N805
        """True if issues are severe."""
        return cls._SEVERE

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
            (
                s.query(HealthCheckIssue)
                .where(
                    HealthCheckIssue.check == cls.name,
                    HealthCheckIssue.value.in_(values),
                )
                .update({"ignore": True})
            )

    def _commit_issues(self) -> None:
        """Commit issues to Portfolio."""
        with self._p.begin_session() as s:
            issues: list[tuple[HealthCheckIssue, str]] = []

            raw = self._issues_raw.copy()
            leftovers: list[HealthCheckIssue] = []
            query = s.query(HealthCheckIssue).where(
                HealthCheckIssue.check == self.name,
            )
            for i in query.yield_per(YIELD_PER):
                msg = raw.pop(i.value, None)
                if msg is None:
                    leftovers.append(i)
                elif self._no_ignores or not i.ignore:
                    issues.append((i, msg))

            for value, msg in raw.items():
                if len(leftovers) == 0:
                    i = HealthCheckIssue(
                        check=self.name,
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
                    issues.append((i, msg))

            # Remaining need to be deleted
            for i in leftovers:
                s.delete(i)

            s.flush()
            self._issues = {i.uri: msg for i, msg in issues}
