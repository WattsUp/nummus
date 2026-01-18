"""Checks for uncleared transactions."""

from __future__ import annotations

import datetime
import textwrap
from typing import override, TYPE_CHECKING

from nummus.health_checks.base import HealthCheck
from nummus.models.account import Account
from nummus.models.base import YIELD_PER
from nummus.models.currency import CURRENCY_FORMATS
from nummus.models.transaction import TransactionSplit

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy import orm

    from nummus.models.currency import Currency


class UnclearedTransactions(HealthCheck):
    """Checks for uncleared transactions."""

    _DESC = textwrap.dedent(
        """\
        Cleared transactions have been imported from bank statements.
        Any uncleared transactions should be imported.""",
    )
    _SEVERE = False

    @override
    def test(self, s: orm.Session) -> None:
        query = s.query(Account).with_entities(
            Account.id_,
            Account.name,
            Account.currency,
        )
        accounts: dict[int, tuple[str, Currency]] = {
            r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
        }
        if len(accounts) == 0:
            self._commit_issues(s, {})
            return
        acct_len = max(len(acct[0]) for acct in accounts.values())
        issues: dict[str, str] = {}

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.id_,
                TransactionSplit.date_ord,
                TransactionSplit.account_id,
                TransactionSplit.payee,
                TransactionSplit.amount,
            )
            .where(TransactionSplit.cleared.is_(False))
        )
        for t_id, date_ord, acct_id, payee, amount in query.yield_per(YIELD_PER):
            t_id: int
            date_ord: int
            acct_id: int
            payee: str
            amount: Decimal
            uri = TransactionSplit.id_to_uri(t_id)

            acct_name, currency = accounts[acct_id]
            cf = CURRENCY_FORMATS[currency]

            msg = (
                f"{datetime.date.fromordinal(date_ord)} -"
                f" {acct_name:{acct_len}}:"
                f" {cf(amount)} to {payee or '[blank]'} is"
                " uncleared"
            )
            issues[uri] = msg

        self._commit_issues(s, issues)
