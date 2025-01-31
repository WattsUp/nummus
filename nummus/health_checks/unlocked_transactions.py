"""Checks for unlocked transactions."""

from __future__ import annotations

import datetime
import textwrap
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from decimal import Decimal


class UnlockedTransactions(Base):
    """Checks for unlocked transactions."""

    _DESC = textwrap.dedent(
        """\
        Locked transactions have been manually verified.
        Any unlocked transactions should be validated and locked.""",
    )
    _SEVERE = False

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            accounts = Account.map_name(s)
            if len(accounts) == 0:
                self._commit_issues()
                return
            acct_len = max(len(acct) for acct in accounts.values())

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.id_,
                    TransactionSplit.date_ord,
                    TransactionSplit.account_id,
                    TransactionSplit.payee,
                    TransactionSplit.amount,
                )
                .where(
                    TransactionSplit.locked.is_(False),
                    TransactionSplit.linked.is_(True),
                )
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
                    " unlocked"
                )
                self._issues_raw[uri] = msg

        self._commit_issues()
