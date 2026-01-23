"""Checks for uncleared transactions."""

from __future__ import annotations

import datetime
import textwrap
from typing import override

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.models.account import Account
from nummus.models.currency import CURRENCY_FORMATS
from nummus.models.transaction import TransactionSplit


class UnclearedTransactions(HealthCheck):
    """Checks for uncleared transactions."""

    _DESC = textwrap.dedent(
        """\
        Cleared transactions have been imported from bank statements.
        Any uncleared transactions should be imported.""",
    )
    _SEVERE = False

    @override
    def test(self) -> None:
        query = Account.query(
            Account.id_,
            Account.name,
            Account.currency,
        )
        accounts = sql.to_dict_tuple(query)
        if len(accounts) == 0:
            self._commit_issues({})
            return
        acct_len = max(len(acct[0]) for acct in accounts.values())
        issues: dict[str, str] = {}

        query = TransactionSplit.query(
            TransactionSplit.id_,
            TransactionSplit.date_ord,
            TransactionSplit.account_id,
            TransactionSplit.payee,
            TransactionSplit.amount,
        ).where(TransactionSplit.cleared.is_(False))
        for t_id, date_ord, acct_id, payee, amount in sql.yield_(query):
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

        self._commit_issues(issues)
