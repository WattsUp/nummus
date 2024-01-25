"""Checks for accounts that had a negative cash balance when they shouldn't."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy
from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, AccountCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from nummus import custom_types as t
    from nummus import portfolio


class OverdrawnAccounts(Base):
    """Checks for accounts that had a negative cash balance when they shouldn't."""

    _NAME = "Overdrawn Accounts"
    _DESC = "Checks for accounts that had a negative cash balance when they shouldn't"
    _SEVERE = True

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        today = datetime.date.today()
        today_ord = today.toordinal()
        with p.get_session() as s:
            # Get a list of accounts subject to overdrawn so not credit and loans
            categories = [
                AccountCategory.CREDIT,
                AccountCategory.LOAN,
                AccountCategory.MORTGAGE,
            ]
            query = (
                s.query(Account)
                .with_entities(Account.id_, Account.name)
                .where(Account.category.not_in(categories))
            )
            accounts: t.DictIntStr = dict(query.all())  # type: ignore[attr-defined]
            acct_ids = set(accounts)

            issues: list[tuple[str, str]] = []

            start_ord = (
                s.query(sqlalchemy.func.min(TransactionSplit.date_ord))
                .where(TransactionSplit.account_id.in_(acct_ids))
                .scalar()
            )
            if start_ord is None:
                # No asset transactions at all
                return
            n = today_ord - start_ord + 1

            for acct_id, name in accounts.items():
                # Get cash holdings across all time
                cash_flow = [None] * n
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

                cash = Decimal(0)
                for i, c in enumerate(cash_flow):
                    if c is None:
                        continue
                    cash += c
                    if cash < 0:
                        date = datetime.date.fromordinal(start_ord + i)
                        source = f"{date} - {name}"
                        issues.append((source, utils.format_financial(c)))

            if len(issues) == 0:
                return
            source_len = max(len(item[0]) for item in issues)
            amount_len = max(len(item[1]) for item in issues)

            for source, amount_str in issues:
                msg = f"{source:{source_len}} {amount_str:>{amount_len}}"
                self._issues.append(msg)
