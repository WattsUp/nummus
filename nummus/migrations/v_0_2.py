"""Migrator to v0.2.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.migrations.base import Migrator
from nummus.models import TransactionCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_2(Migrator):  # noqa: N801
    """Migrator to v0.2.0."""

    _VERSION = "0.2.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> None:

        with p.begin_session() as s:
            # Update TransactionSplit to add text_fields
            self.add_column(s, TransactionSplit, TransactionSplit.text_fields)
            self.migrate_schemas(s, TransactionSplit)
            query = s.query(TransactionSplit)
            for t_split in query.yield_per(YIELD_PER):
                # Setting a text field with update text_fields
                t_split.payee = t_split.payee

            # Update TransactionCategory.name to be filtered version of emoji_name
            query = s.query(TransactionCategory)
            for t_cat in query.yield_per(YIELD_PER):
                t_cat.emoji_name = t_cat.emoji_name

        self.update_db_version(p)
