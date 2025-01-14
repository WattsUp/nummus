"""Checks for transactions with same amount and date."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, Transaction, YIELD_PER

if TYPE_CHECKING:
    from decimal import Decimal


class DuplicateTransactions(Base):
    """Checks for transactions with same amount, date, and statement."""

    _DESC = "Checks for transactions with same amount, date, and statement."
    _SEVERE = True

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            accounts = Account.map_name(s)

            issues: list[tuple[str, str, str]] = []

            query = (
                s.query(Transaction)
                .with_entities(
                    Transaction.date_ord,
                    Transaction.account_id,
                    Transaction.amount,
                )
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

                for uri, source, amount_str in issues:
                    msg = f"{source:{source_len}} {amount_str:>{amount_len}}"
                    self._issues_raw[uri] = msg

        self._commit_issues()
