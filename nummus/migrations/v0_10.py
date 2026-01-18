"""Migrator to v0.10.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.migrations.base import Migrator
from nummus.models.base import YIELD_PER
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_10(Migrator):
    """Migrator to v0.10.0."""

    _VERSION = "0.10.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:

        comments: list[str] = []

        with p.begin_session() as s:
            self.rename_column(
                s,
                TransactionCategory,
                "essential",
                "essential_spending",
            )

            query = s.query(HealthCheckIssue)
            for issue in query.yield_per(YIELD_PER):
                issue.check = issue.check.capitalize()

        return comments
