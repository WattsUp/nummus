"""Checks for non-zero net transfers."""

from __future__ import annotations

import datetime
import textwrap
from decimal import Decimal

from typing_extensions import override

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import Account, TransactionCategory, TransactionSplit, YIELD_PER
from nummus.models.transaction_category import TransactionCategoryGroup


class UnbalancedTransfers(Base):
    """Checks for non-zero net transfers."""

    _NAME = "Unbalanced transfers"
    _DESC = textwrap.dedent(
        """\
        Transfers move money between accounts so none should be lost.
        If there are transfer fees, add that as a separate transaction.""",
    )
    _SEVERE = True

    @override
    def test(self) -> None:
        with self._p.get_session() as s:
            cat_transfers_ids = {
                t_cat_id
                for t_cat_id, in s.query(TransactionCategory.id_)
                .where(TransactionCategory.group == TransactionCategoryGroup.TRANSFER)
                .all()
            }

            accounts = Account.map_name(s)

            def add_issue(date_ord: int, splits: list[tuple[str, Decimal]]) -> None:
                date = datetime.date.fromordinal(date_ord)
                date_str = date.isoformat()
                msg_l = [
                    f"{date}: Sum of transfers on this day are non-zero",
                ]

                # Remove any that are exactly equal since those are probably
                # balanced amongst themselves
                i = 0
                # Do need to run len(current_splits) every time since it
                # will change length during iteration
                while i < len(splits):
                    # Look for inverse amount in remaining splits
                    v_search = -splits[i][1]
                    found_any = False
                    for ii in range(i + 1, len(splits)):
                        if v_search == splits[ii][1]:
                            # If found, pop both positive and negative ones
                            splits.pop(ii)
                            splits.pop(i)
                            found_any = True
                            break
                    # Don't increase iterator if popped any since there is a
                    # new value at i
                    if not found_any:
                        i += 1

                splits = sorted(
                    splits,
                    key=lambda item: (item[0], item[1]),
                )
                acct_len = max(len(item[0]) for item in splits)
                msg_l.extend(
                    f"  {acct:{acct_len}}: "
                    f"{utils.format_financial(amount, plus=True):>14}"
                    for acct, amount in splits
                )
                self._issues_raw[date_str] = "\n".join(msg_l)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.account_id,
                    TransactionSplit.date_ord,
                    TransactionSplit.amount,
                )
                .where(TransactionSplit.category_id.in_(cat_transfers_ids))
                .order_by(TransactionSplit.date_ord)
            )
            current_date_ord: int | None = None
            total = Decimal(0)
            current_splits: list[tuple[str, Decimal]] = []
            for acct_id, date_ord, amount in query.yield_per(YIELD_PER):
                acct_id: int
                date_ord: int
                amount: Decimal
                if current_date_ord is None:
                    current_date_ord = date_ord
                if date_ord != current_date_ord:
                    if total != 0:
                        add_issue(current_date_ord, current_splits)
                    current_date_ord = date_ord
                    total = Decimal(0)
                    current_splits = []

                total += amount
                current_splits.append((accounts[acct_id], amount))

            if total != 0 and current_date_ord is not None:
                add_issue(current_date_ord, current_splits)

        self._commit_issues()
