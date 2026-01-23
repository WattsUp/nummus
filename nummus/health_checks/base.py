"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from nummus import sql, utils
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.utils import update_rows


class HealthCheck(ABC):
    """Base health check class."""

    _DESC: ClassVar[str]
    _SEVERE: ClassVar[bool]

    def __init__(
        self,
        *,
        no_ignores: bool = False,
        **_: object,
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
    def test(self) -> None:
        """Run the health check on a portfolio."""
        raise NotImplementedError

    @classmethod
    def ignore(cls, values: list[str] | set[str]) -> None:
        """Ignore false positive issues.

        Args:
            values: List of issues to ignore

        """
        (
            HealthCheckIssue.query()
            .where(
                HealthCheckIssue.check == cls.name(),
                HealthCheckIssue.value.in_(values),
            )
            .update({"ignore": True})
        )

    def _commit_issues(self, issues: dict[str, str]) -> None:
        """Commit issues to Portfolio.

        Args:
            issues: dict{value: message}

        """
        query = HealthCheckIssue.query(HealthCheckIssue.value).where(
            HealthCheckIssue.check == self.name(),
            HealthCheckIssue.ignore.is_(True),
        )
        ignored = set(sql.col0(query))

        updates: dict[object, dict[str, object]] = {
            value: {"check": self.name(), "ignore": value in ignored, "msg": msg}
            for value, msg in issues.items()
        }
        query = HealthCheckIssue.query().where(
            HealthCheckIssue.check == self.name(),
        )
        update_rows(HealthCheckIssue, query, "value", updates)

        query = HealthCheckIssue.query(
            HealthCheckIssue.id_,
            HealthCheckIssue.msg,
        ).where(
            HealthCheckIssue.check == self.name(),
        )
        if not self._no_ignores:
            query = query.where(HealthCheckIssue.ignore.is_(False))
        self._issues = {
            HealthCheckIssue.id_to_uri(id_): msg for id_, msg in sql.yield_(query)
        }
