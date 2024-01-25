"""Checks for empty fields that are better when populated."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus import exceptions as exc
from nummus.health_checks.base import Base
from nummus.models import (
    Account,
    Asset,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from nummus import portfolio


class EmptyFields(Base):
    """Checks for empty fields that are better when populated."""

    _NAME = "Empty Fields"
    _DESC = "Checks for empty fields that are better when populated"
    _SEVERE = False

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        with p.get_session() as s:
            accounts = Account.map_name(s)

            # List of (source, field)
            issues: list[tuple[str, str]] = []

            query = s.query(Account.name).where(Account.number.is_(None))
            for (name,) in query.yield_per(YIELD_PER):
                issues.append((f"Account {name}", "has an empty number"))

            query = s.query(Asset.name).where(Asset.description.is_(None))
            for (name,) in query.yield_per(YIELD_PER):
                issues.append((f"Asset {name}", "has an empty description"))

            txn_fields = [
                TransactionSplit.payee,
                TransactionSplit.description,
            ]
            for field in txn_fields:
                query = (
                    s.query(TransactionSplit)
                    .with_entities(
                        TransactionSplit.date_ord,
                        TransactionSplit.account_id,
                    )
                    .where(field.is_(None))
                )
                for date_ord, acct_id in query.yield_per(YIELD_PER):
                    date_ord: int
                    acct_id: int
                    date = datetime.date.fromordinal(date_ord)
                    source = f"{date} - {accounts[acct_id]}"
                    issues.append((source, f"has an empty {field.key}"))

            try:
                t_cat_uncategorized = (
                    s.query(TransactionCategory.id_)
                    .where(TransactionCategory.name == "Uncategorized")
                    .one()[0]
                )
            except exc.NoResultFound as e:
                msg = "Category Uncategorized not found"
                raise exc.ProtectedObjectNotFoundError(msg) from e
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                )
                .where(TransactionSplit.category_id == t_cat_uncategorized)
            )
            for date_ord, acct_id in query.yield_per(YIELD_PER):
                date_ord: int
                acct_id: int
                date = datetime.date.fromordinal(date_ord)
                source = f"{date} - {accounts[acct_id]}"
                issues.append((source, "is uncategorized"))

            if len(issues) == 0:
                return

            source_len = max(len(item[0]) for item in issues)
            for source, field in issues:
                msg = f"{source:{source_len}} {field}"
                self._issues.append(msg)
