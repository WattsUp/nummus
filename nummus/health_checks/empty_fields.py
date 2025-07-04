"""Checks for empty fields that are better when populated."""

from __future__ import annotations

import datetime

from typing_extensions import override

from nummus.health_checks.base import Base
from nummus.models import (
    Account,
    Asset,
    TransactionCategory,
    TransactionSplit,
    YIELD_PER,
)


class EmptyFields(Base):
    """Checks for empty fields that are better when populated."""

    _DESC = "Checks for empty fields that are better when populated."
    _SEVERE = False

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            accounts = Account.map_name(s)

            # List of (uri, source, field)
            issues: list[tuple[str, str, str]] = []

            query = (
                s.query(Account)
                .with_entities(Account.id_, Account.name)
                .where(Account.number.is_(None))
            )
            for acct_id, name in query.yield_per(YIELD_PER):
                acct_id: int
                name: str
                uri = Account.id_to_uri(acct_id)
                issues.append(
                    (f"{uri}.number", f"Account {name}", "has an empty number"),
                )

            query = (
                s.query(Asset)
                .with_entities(Asset.id_, Asset.name)
                .where(Asset.description.is_(None))
            )
            for a_id, name in query.yield_per(YIELD_PER):
                a_id: int
                name: str
                uri = Asset.id_to_uri(a_id)
                issues.append(
                    (f"{uri}.description", f"Asset {name}", "has an empty description"),
                )

            txn_fields = [
                TransactionSplit.payee,
            ]
            for field in txn_fields:
                query = (
                    s.query(TransactionSplit)
                    .with_entities(
                        TransactionSplit.id_,
                        TransactionSplit.date_ord,
                        TransactionSplit.account_id,
                    )
                    .where(
                        field.is_(None),
                        TransactionSplit.asset_id.is_(None),
                    )
                )
                for t_id, date_ord, acct_id in query.yield_per(YIELD_PER):
                    t_id: int
                    date_ord: int
                    acct_id: int
                    uri = TransactionSplit.id_to_uri(t_id)

                    date = datetime.date.fromordinal(date_ord)
                    source = f"{date} - {accounts[acct_id]}"
                    issues.append(
                        (f"{uri}.{field.key}", source, f"has an empty {field.key}"),
                    )

            uncategorized_id, _ = TransactionCategory.uncategorized(s)
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.id_,
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                )
                .where(TransactionSplit.category_id == uncategorized_id)
            )
            for t_id, date_ord, acct_id in query.yield_per(YIELD_PER):
                t_id: int
                date_ord: int
                acct_id: int
                uri = TransactionSplit.id_to_uri(t_id)

                date = datetime.date.fromordinal(date_ord)
                source = f"{date} - {accounts[acct_id]}"
                issues.append((f"{uri}.category", source, "is uncategorized"))

            if len(issues) != 0:
                source_len = max(len(item[1]) for item in issues)
                for uri, source, field in issues:
                    msg = f"{source:{source_len}} {field}"
                    self._issues_raw[uri] = msg

        self._commit_issues()
