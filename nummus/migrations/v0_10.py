"""Migrator to v0.10.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.migrations.base import Migrator
from nummus.models import (
    TransactionCategory,
)

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_10(Migrator):  # noqa: N801
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

        return comments
