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
        ignores = self.get_ignores(p)
        with p.get_session() as s:
            accounts = Account.map_name(s)

            # List of (source, field)
            issues: list[tuple[str, str]] = []

            query = (
                s.query(Account)
                .with_entities(Account.id_, Account.name)
                .where(Account.number.is_(None))
            )
            for acct_id, name in query.yield_per(YIELD_PER):
                acct_id: int
                name: str
                uri = Account.id_to_uri(acct_id)
                if uri in ignores:
                    continue
                issues.append((f"Account {name}", "has an empty number"))

            query = (
                s.query(Asset)
                .with_entities(Asset.id_, Asset.name)
                .where(Asset.description.is_(None))
            )
            for a_id, name in query.yield_per(YIELD_PER):
                a_id: int
                name: str
                uri = Asset.id_to_uri(a_id)
                if uri in ignores:
                    continue
                issues.append((f"Asset {name}", "has an empty description"))

            txn_fields = [
                TransactionSplit.payee,
                TransactionSplit.description,
            ]
            for field in txn_fields:
                query = (
                    s.query(TransactionSplit)
                    .with_entities(
                        TransactionSplit.id_,
                        TransactionSplit.date_ord,
                        TransactionSplit.account_id,
                    )
                    .where(field.is_(None))
                )
                for t_id, date_ord, acct_id in query.yield_per(YIELD_PER):
                    t_id: int
                    date_ord: int
                    acct_id: int
                    uri = TransactionSplit.id_to_uri(t_id)
                    if uri in ignores:
                        continue

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
                    TransactionSplit.id_,
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                )
                .where(TransactionSplit.category_id == t_cat_uncategorized)
            )
            for t_id, date_ord, acct_id in query.yield_per(YIELD_PER):
                t_id: int
                date_ord: int
                acct_id: int
                uri = TransactionSplit.id_to_uri(t_id)
                if uri in ignores:
                    continue

                date = datetime.date.fromordinal(date_ord)
                source = f"{date} - {accounts[acct_id]}"
                issues.append((source, "is uncategorized"))

            if len(issues) == 0:
                return

            source_len = max(len(item[0]) for item in issues)
            for source, field in issues:
                msg = f"{source:{source_len}} {field}"
                self._issues.append(msg)
