"""Migrator to v0.2.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.migrations.base import Migrator
from nummus.models import TransactionCategory, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_2(Migrator):  # noqa: N801
    """Migrator to v0.2.0."""

    _VERSION = "0.2.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> None:

        with p.begin_session() as s:
            query = s.query(TransactionCategory)
            for t_cat in query.yield_per(YIELD_PER):
                t_cat.emoji_name = t_cat.emoji_name

        self.update_db_version(p)
