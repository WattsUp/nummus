"""Checks for transactions with same amount and date."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, Transaction, YIELD_PER

if TYPE_CHECKING:
    from decimal import Decimal


class DuplicateTransactions(Base):
    """Checks for transactions with same amount and date."""

    _NAME = "Duplicate Transactions"
    _DESC = "Checks for transactions with same amount and date."
    _SEVERE = True

    @override
    def test(self) -> None:
        with self._p.get_session() as s:
            accounts = Account.map_name(s)

            issues: list[tuple[str, str, str]] = []

            query = (
                s.query(Transaction)
                .with_entities(
                    Transaction.id_,
                    Transaction.date_ord,
                    Transaction.account_id,
                    Transaction.amount,
                )
                .group_by(
                    Transaction.date_ord,
                    Transaction.account_id,
                    Transaction.amount,
                )
                .having(sqlalchemy.func.count(Transaction.id_) > 1)
            )
            for t_id, date_ord, acct_id, amount in query.yield_per(YIELD_PER):
                t_id: int
                date_ord: int
                acct_id: int
                amount: Decimal
                uri = Transaction.id_to_uri(t_id)

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