"""Portfolio health checks."""

from __future__ import annotations

import textwrap
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus import portfolio


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


class DatabaseIntegrity(Base):
    """Checks for issues in the underlying SQL database."""

    _NAME = "Database integrity"
    _DESC = "Checks for issues in the underlying SQL database."
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = []


class UnbalancedTransfers(Base):
    """Checks for non-zero net transfers."""

    _NAME = "Unbalanced tranfers"
    _DESC = textwrap.dedent("""\
        Transfers move money between accounts so none should be lost.
        If there are transfer fees, add that as a separate transaction.""")
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = [
            textwrap.dedent("""\
            2024-01-01: Sum of transfers on this day are non-zero
                'Monkey Bank Checking' +$100
                'Monkey Bank Savings' -$100"""),
        ]


class UnbalancedCreditCardPayments(Base):
    """Checks for non-zero net credit card payments."""

    _NAME = "Unbalanced credit card payments"
    _DESC = textwrap.dedent("""\
        Credit card payments are transfers so none should be lost.
        If there interest incurred, add that as a separate transaction.""")
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = []


class MissingAssetValuations(Base):
    """Checks if an asset is held without any valuations."""

    _NAME = "Missing asset valuations"
    _DESC = "Checks if an asset is held without any valuations"
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = []


class Typos(Base):
    """Checks for very similar fields and common typos."""

    _NAME = "Typos"
    _DESC = "Checks for very similar fields and common typos."
    _SEVERE = False

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = []


class UnlockedTransactions(Base):
    """Checks for unlocked transactions."""

    _NAME = "Unlocked transactions"
    _DESC = textwrap.dedent("""\
        Locked transactions have been manually verified.
        Any unlocked transactions should be validated and locked.""")
    _SEVERE = False

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        self._issues = [
            "2024-01-01 'Monkey Bank Checking': $100 for 'Corner Store'",
        ]


# List of all checks to test
CHECKS: list[type[Base]] = [
    DatabaseIntegrity,
    UnbalancedTransfers,
    UnbalancedCreditCardPayments,
    MissingAssetValuations,
    Typos,
    UnlockedTransactions,
]
