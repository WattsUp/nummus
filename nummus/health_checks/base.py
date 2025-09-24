"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, TYPE_CHECKING

from nummus import utils
from nummus.models import HealthCheckIssue, update_rows, YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


class Base(ABC):
    """Base health check class."""

    _DESC: ClassVar[str]
    _SEVERE: ClassVar[bool]

    def __init__(
        self,
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
        self._issues: dict[str, str] = {}
        self._no_ignores = no_ignores

    @classmethod
    def name(cls) -> str:
        """Health check name.

        Returns:
            str

        """
        return utils.camel_to_snake(cls.__name__).replace("_", " ").capitalize()

    @classmethod
    def description(cls) -> str:
        """Health check description.

        Returns:
            str

        """
        return cls._DESC

    @property
    def issues(self) -> dict[str, str]:
        """List of issues this check found, dict{uri: msg}."""
        return self._issues

    @property
    def any_issues(self) -> bool:
        """True if check found any issues."""
        return len(self._issues) != 0

    @classmethod
    def is_severe(cls) -> bool:
        """Check if issues are severe.

        Returns:
            True if issues are severe

        """
        return cls._SEVERE

    @abstractmethod
    def test(self, s: orm.Session) -> None:
        """Run the health check on a portfolio.

        Args:
            s: SQL session to use

        """
        raise NotImplementedError

    @classmethod
    def ignore(cls, s: orm.Session, values: list[str] | set[str]) -> None:
        """Ignore false positive issues.

        Args:
            s: SQL session to use
            values: List of issues to ignore

        """
        (
            s.query(HealthCheckIssue)
            .where(
                HealthCheckIssue.check == cls.name(),
                HealthCheckIssue.value.in_(values),
            )
            .update({"ignore": True})
        )

    def _commit_issues(self, s: orm.Session, issues: dict[str, str]) -> None:
        """Commit issues to Portfolio.

        Args:
            s: SQL session to use
            issues: dict{value: message}

        """
        query = s.query(HealthCheckIssue.value).where(
            HealthCheckIssue.check == self.name(),
            HealthCheckIssue.ignore.is_(True),
        )
        ignored = {r[0] for r in query.yield_per(YIELD_PER)}

        updates: dict[object, dict[str, object]] = {
            value: {"check": self.name(), "ignore": value in ignored, "msg": msg}
            for value, msg in issues.items()
        }
        query = s.query(HealthCheckIssue).where(
            HealthCheckIssue.check == self.name(),
        )
        update_rows(s, HealthCheckIssue, query, "value", updates)
        s.flush()

        query = (
            s.query(HealthCheckIssue)
            .with_entities(HealthCheckIssue.id_, HealthCheckIssue.msg)
            .where(
                HealthCheckIssue.check == self.name(),
            )
        )
        if not self._no_ignores:
            query = query.where(HealthCheckIssue.ignore.is_(False))
        self._issues = {
            HealthCheckIssue.id_to_uri(id_): msg
            for id_, msg in query.yield_per(YIELD_PER)
        }
