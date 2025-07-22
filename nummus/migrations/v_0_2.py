"""Migrator to v0.2.0."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func
from typing_extensions import override

from nummus.migrations.base import Migrator
from nummus.models import (
    Account,
    Asset,
    Base,
    BudgetGroup,
    Config,
    HealthCheckIssue,
    ImportedFile,
    Transaction,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_2(Migrator):  # noqa: N801
    """Migrator to v0.2.0."""

    _VERSION = "0.2.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:

        comments: list[str] = []

        with p.begin_session() as s:
            # Update TransactionSplit to add text_fields
            self.add_column(s, TransactionSplit, TransactionSplit.text_fields)
            self.rename_column(s, TransactionSplit, "description", "memo")
            self.rename_column(s, TransactionSplit, "linked", "cleared")
            self.drop_column(s, TransactionSplit, "locked")

        with p.begin_session() as s:
            # Update Transaction to add payee
            self.add_column(s, Transaction, Transaction.payee)
            self.rename_column(s, Transaction, "linked", "cleared")
            self.drop_column(s, Transaction, "locked")

        with p.begin_session() as s:
            # Check which ones have more than one payee
            accounts = Account.map_name(s)
            query = (
                s.query(TransactionSplit)
                .group_by(TransactionSplit.parent_id)
                .having(func.count(TransactionSplit.payee.distinct()) > 1)
                .order_by(TransactionSplit.date_ord)
            )
            for t_split in query.yield_per(YIELD_PER):
                msg = (
                    "This transaction had multiple payees, only one allowed: "
                    f"{t_split.date} {accounts[t_split.account_id]}, please validate"
                )
                comments.append(msg)

            sub_query = (
                s.query(TransactionSplit.payee)
                .where(
                    TransactionSplit.parent_id == Transaction.id_,
                )
                .scalar_subquery()
            )
            s.query(Transaction).update(
                {Transaction.payee: sub_query},
            )

        with p.begin_session() as s:
            # Update text_fields after payee is set
            query = s.query(TransactionSplit)
            for t_split in query.yield_per(YIELD_PER):
                t_split.parent = t_split.parent
                t_split.memo = t_split.memo

            # Update TransactionCategory.name to be filtered version of emoji_name
            query = s.query(TransactionCategory)
            for t_cat in query.yield_per(YIELD_PER):
                t_cat.emoji_name = t_cat.emoji_name

        # Update string_column_args on all models
        models: list[type[Base]] = [
            Account,
            Asset,
            BudgetGroup,
            Config,
            ImportedFile,
            HealthCheckIssue,
            Transaction,
            TransactionCategory,
            TransactionSplit,
        ]
        self.pending_schema_updates.update(models)

        return comments
