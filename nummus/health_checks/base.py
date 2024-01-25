"""Portfolio health checks."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

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
