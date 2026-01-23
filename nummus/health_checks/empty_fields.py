"""Checks for empty fields that are better when populated."""

from __future__ import annotations

import datetime
from typing import override

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.transaction import Transaction, TransactionSplit
from nummus.models.transaction_category import TransactionCategory


class EmptyFields(HealthCheck):
    """Checks for empty fields that are better when populated."""

    _DESC = "Checks for empty fields that are better when populated."
    _SEVERE = False

    @override
    def test(self) -> None:
        accounts = Account.map_name()

        # List of (uri, source, field)
        issues: list[tuple[str, str, str]] = []

        query = Account.query(Account.id_, Account.name).where(Account.number.is_(None))
        for acct_id, name in sql.yield_(query):
            uri = Account.id_to_uri(acct_id)
            issues.append(
                (f"{uri}.number", f"Account {name}", "has an empty number"),
            )

        query = Asset.query(Asset.id_, Asset.name).where(
            Asset.description.is_(None),
        )
        for a_id, name in sql.yield_(query):
            uri = Asset.id_to_uri(a_id)
            issues.append(
                (f"{uri}.description", f"Asset {name}", "has an empty description"),
            )

        query = Transaction.query(
            Transaction.id_,
            Transaction.date_ord,
            Transaction.account_id,
        ).where(
            Transaction.payee.is_(None),
        )
        for t_id, date_ord, acct_id in sql.yield_(query):
            uri = Transaction.id_to_uri(t_id)

            date = datetime.date.fromordinal(date_ord)
            source = f"{date} - {accounts[acct_id]}"
            issues.append(
                (f"{uri}.payee", source, "has an empty payee"),
            )

        uncategorized_id, _ = TransactionCategory.uncategorized()
        query = TransactionSplit.query(
            TransactionSplit.id_,
            TransactionSplit.date_ord,
            TransactionSplit.account_id,
        ).where(TransactionSplit.category_id == uncategorized_id)
        for t_id, date_ord, acct_id in sql.yield_(query):
            uri = TransactionSplit.id_to_uri(t_id)

            date = datetime.date.fromordinal(date_ord)
            source = f"{date} - {accounts[acct_id]}"
            issues.append((f"{uri}.category", source, "is uncategorized"))

        source_len = max(len(item[1]) for item in issues) if issues else 0

        self._commit_issues(
            {uri: f"{source:{source_len}} {field}" for uri, source, field in issues},
        )
