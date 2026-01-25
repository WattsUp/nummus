"""Migrator to v0.2.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from sqlalchemy import func

from nummus import sql
from nummus.migrations.base import Migrator
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.budget import BudgetGroup
from nummus.models.config import Config
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.imported_file import ImportedFile
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from nummus import portfolio
    from nummus.models.base import Base


class MigratorV0_2(Migrator):
    """Migrator to v0.2.0."""

    _VERSION = "0.2.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:

        comments: list[str] = []

        with p.begin_session():
            # Update TransactionSplit to add text_fields
            self.add_column(TransactionSplit, TransactionSplit.text_fields)
            self.rename_column(TransactionSplit, "description", "memo")
            self.rename_column(TransactionSplit, "linked", "cleared")
            self.drop_column(TransactionSplit, "locked")

        with p.begin_session():
            # Update Transaction to add payee
            self.add_column(Transaction, Transaction.payee)
            self.rename_column(Transaction, "linked", "cleared")
            self.drop_column(Transaction, "locked")

        with p.begin_session():
            # Check which ones have more than one payee
            accounts = Account.map_name()
            query = (
                TransactionSplit.query()
                .group_by(TransactionSplit.parent_id)
                .having(func.count(TransactionSplit.payee.distinct()) > 1)
                .order_by(TransactionSplit.date_ord)
            )
            for t_split in sql.yield_(query):
                msg = (
                    "This transaction had multiple payees, only one allowed: "
                    f"{t_split.date} {accounts[t_split.account_id]}, please validate"
                )
                comments.append(msg)

            sub_query = (
                TransactionSplit.query(TransactionSplit.payee)
                .where(
                    TransactionSplit.parent_id == Transaction.id_,
                )
                .scalar_subquery()
            )
            Transaction.query().update(
                {Transaction.payee: sub_query},
            )

        with p.begin_session():
            n_batch = 100
            # Update text_fields after payee is set
            for t_split in TransactionSplit.all():
                t_split.parent = t_split.parent
                t_split.memo = t_split.memo

            # Update TransactionCategory.name to be filtered version of emoji_name
            has_more = True
            offset = 0
            while has_more:
                query = (
                    TransactionCategory.query(
                        TransactionCategory.id_,
                        TransactionCategory.emoji_name,
                    )
                    .order_by(TransactionCategory.id_)
                    .offset(offset)
                    .limit(n_batch)
                )
                values = {
                    id_: TransactionCategory.clean_emoji_name(v)
                    for id_, v in sql.yield_(query)
                }
                TransactionCategory.query().where(
                    TransactionCategory.id_.in_(values),
                ).update(
                    {
                        TransactionCategory.name: sql.case(
                            values,
                            value=TransactionCategory.id_,
                        ),
                    },
                )
                has_more = len(values) >= n_batch

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
