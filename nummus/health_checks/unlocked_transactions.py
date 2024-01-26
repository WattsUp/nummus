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
    from nummus import custom_types as t
    from nummus import portfolio


class UnlockedTransactions(Base):
    """Checks for unlocked transactions."""

    _NAME = "Unlocked transactions"
    _DESC = textwrap.dedent("""\
        Locked transactions have been manually verified.
        Any unlocked transactions should be validated and locked.""")
    _SEVERE = False

    @override
    def test(self, p: portfolio.Portfolio) -> None:
        silences = self.get_silences(p)
        with p.get_session() as s:
            accounts = Account.map_name(s)
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
                .where(TransactionSplit.locked.is_(False))
            )
            for t_id, date_ord, acct_id, payee, amount in query.yield_per(YIELD_PER):
                t_id: int
                date_ord: int
                acct_id: int
                payee: str
                amount: t.Real
                uri = TransactionSplit.id_to_uri(t_id)
                if uri in silences:
                    continue

                msg = (
                    f"{datetime.date.fromordinal(date_ord)} -"
                    f" {accounts[acct_id]:{acct_len}}:"
                    f" {utils.format_financial(amount)} to {payee} is unlocked"
                )
                self._issues.append(msg)
