"""Migrator to v0.11.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.migrations.base import Migrator
from nummus.models import (
    AssetSector,
    AssetSplit,
    AssetValuation,
    BudgetAssignment,
    Target,
    Transaction,
    TransactionSplit,
)

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_11(Migrator):
    """Migrator to v0.11.0."""

    _VERSION = "0.11.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        _ = p

        comments: list[str] = []

        # Just need to migrate schemas to add indices
        self.pending_schema_updates.update(
            {
                AssetSector,
                AssetSplit,
                AssetValuation,
                BudgetAssignment,
                Target,
                Transaction,
                TransactionSplit,
            },
        )

        return comments
