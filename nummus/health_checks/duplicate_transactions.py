"""Checks for transactions with same amount and date."""

from __future__ import annotations

import datetime
from typing import override, TYPE_CHECKING

from sqlalchemy import func

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, Transaction, YIELD_PER

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy import orm


class DuplicateTransactions(Base):
    """Checks for transactions with same amount, date, and statement."""

    _DESC = "Checks for transactions with same amount, date, and statement."
    _SEVERE = True

    @override
    def test(self, s: orm.Session) -> None:
        accounts = Account.map_name(s)

        issues: list[tuple[str, str, str]] = []

        query = (
            s.query(Transaction)
            .with_entities(
                Transaction.date_ord,
                Transaction.account_id,
                Transaction.amount,
            )
            # Dividends often occur on the same day with a zero Transaction.amount
            .where(Transaction.amount != 0)
            .group_by(
                Transaction.date_ord,
                Transaction.account_id,
                Transaction.amount,
                Transaction.statement,
            )
            .order_by(Transaction.date_ord)
            .having(func.count() > 1)
        )
        for date_ord, acct_id, amount in query.yield_per(YIELD_PER):
            date_ord: int
            acct_id: int
            amount: Decimal
            amount_raw = Transaction.amount.type.process_bind_param(amount, None)
            # Create a robust uri for this duplicate
            uri = f"{acct_id}.{date_ord}.{amount_raw}"

            date = datetime.date.fromordinal(date_ord)
            source = f"{date} - {accounts[acct_id]}"
            issues.append((uri, source, utils.format_financial(amount)))

        if len(issues) != 0:
            source_len = max(len(item[1]) for item in issues)
            amount_len = max(len(item[2]) for item in issues)
        else:
            source_len = 0
            amount_len = 0

        self._commit_issues(
            s,
            {
                uri: f"{source:{source_len}}: {amount_str:>{amount_len}}"
                for uri, source, amount_str in issues
            },
        )
