"""Checks for accounts that had a negative cash balance when they shouldn't."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import override, TYPE_CHECKING

from sqlalchemy import func

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import (
    Account,
    AccountCategory,
    query_to_dict,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from sqlalchemy import orm


class OverdrawnAccounts(Base):
    """Checks for accounts that had a negative cash balance when they shouldn't."""

    _DESC = "Checks for accounts that had a negative cash balance when they shouldn't."
    _SEVERE = True

    @override
    def test(self, s: orm.Session) -> None:
        # Get a list of accounts subject to overdrawn so not credit and loans
        categories_exclude = [
            AccountCategory.CREDIT,
            AccountCategory.LOAN,
            AccountCategory.MORTGAGE,
        ]
        query = (
            s.query(Account)
            .with_entities(Account.id_, Account.name)
            .where(Account.category.not_in(categories_exclude))
        )
        accounts: dict[int, str] = query_to_dict(query)
        acct_ids = set(accounts)

        issues: list[tuple[str, str, str]] = []

        start_ord, end_ord = (
            s.query(
                func.min(TransactionSplit.date_ord),
                func.max(TransactionSplit.date_ord),
            )
            .where(TransactionSplit.account_id.in_(acct_ids))
            .one()
        )
        start_ord: int | None
        end_ord: int | None
        if start_ord is None or end_ord is None:
            # No asset transactions at all
            self._commit_issues(s, {})
            return
        n = end_ord - start_ord + 1

        for acct_id, name in accounts.items():
            # Get cash holdings across all time
            cash_flow: list[Decimal | None] = [None] * n
            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.date_ord,
                    TransactionSplit.amount,
                )
                .where(
                    TransactionSplit.account_id == acct_id,
                )
            )
            for date_ord, amount in query.yield_per(YIELD_PER):
                date_ord: int
                amount: Decimal

                i = date_ord - start_ord

                v = cash_flow[i]
                cash_flow[i] = amount if v is None else v + amount

            cash = Decimal()
            signalled = False
            for i, c in enumerate(cash_flow):
                date_ord = start_ord + i
                if c is None:
                    continue
                cash += c
                # Only report the first time an txn overdraws the account
                # Since it is likely to upset all following balances
                if cash < 0 and not signalled:
                    signalled = True
                    date = datetime.date.fromordinal(date_ord)
                    uri = f"{acct_id}.{date_ord}"
                    source = f"{date} - {name}"
                    issues.append((uri, source, utils.format_financial(cash)))
                elif cash >= 0:
                    signalled = False

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
