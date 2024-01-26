"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nummus.models import HealthCheckSilence, YIELD_PER

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus import portfolio

# TODO (WattsUp): Add a silence mechanism to hush false positives


class Base(ABC):
    """Base health check class."""

    _NAME: str = ""
    _DESC: str = ""
    _SEVERE: bool = False

    def __init__(self) -> None:
        """Initialize Base health check."""
        super().__init__()
        self._issues: t.Strings = []

    @property
    def name(self) -> str:
        """Health check name."""
        return self._NAME

    @property
    def description(self) -> str:
        """Health check description."""
        return self._DESC

    @property
    def issues(self) -> t.Strings:
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
    def silence(cls, p: portfolio.Portfolio, values: list[str] | set[str]) -> None:
        """Silence false positive issues.

        Args:
            p: Portfolio to test
            values: List of issues to silence
        """
        with p.get_session() as s:
            query = s.query(HealthCheckSilence.value).where(
                HealthCheckSilence.check == cls._NAME,
                HealthCheckSilence.value.in_(values),
            )
            duplicates = [row[0] for row in query.yield_per(YIELD_PER)]
            values = [v for v in values if v not in duplicates]
            for v in values:
                c = HealthCheckSilence(check=cls._NAME, value=v)
                s.add(c)
            s.commit()

    @classmethod
    def get_silences(cls, p: portfolio.Portfolio) -> list[str]:
        """Get list of silences for this check.

        Args:
            p: Portfolio to test

        Returns:
            List of silences, interpretation depends on specific check
        """
        with p.get_session() as s:
            query = s.query(HealthCheckSilence.value).where(
                HealthCheckSilence.check == cls._NAME,
            )
            return [row[0] for row in query.yield_per(YIELD_PER)]
