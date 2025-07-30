"""Checks for uncleared transactions."""

from __future__ import annotations

import datetime
import textwrap
from typing import override, TYPE_CHECKING

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from decimal import Decimal

    from sqlalchemy import orm


class UnclearedTransactions(Base):
    """Checks for unlinked transactions."""

    _DESC = textwrap.dedent(
        """\
        Cleared transactions have been imported from bank statements.
        Any uncleared transactions should be imported.""",
    )
    _SEVERE = False

    @override
    def test(self, s: orm.Session) -> None:
        accounts = Account.map_name(s)
        if len(accounts) == 0:
            self._commit_issues(s, {})
            return
        acct_len = max(len(acct) for acct in accounts.values())
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

            msg = (
                f"{datetime.date.fromordinal(date_ord)} -"
                f" {accounts[acct_id]:{acct_len}}:"
                f" {utils.format_financial(amount)} to {payee or '[blank]'} is"
                " uncleared"
            )
            issues[uri] = msg

        self._commit_issues(s, issues)
