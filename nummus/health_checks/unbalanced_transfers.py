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

    _DESC = textwrap.dedent(
        """\
        Transfers move money between accounts so none should be lost.
        If there are transfer fees, add that as a separate transaction.""",
    )
    _SEVERE = True

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            query = s.query(TransactionCategory.id_, TransactionCategory.name).where(
                TransactionCategory.group == TransactionCategoryGroup.TRANSFER,
            )
            cat_transfers_ids: dict[int, str] = dict(query.all())  # type: ignore[attr-defined]

            accounts = Account.map_name(s)

            def add_issue(
                date_ord: int,
                categories: dict[int, list[tuple[str, Decimal]]],
            ) -> None:
                date = datetime.date.fromordinal(date_ord)
                date_str = date.isoformat()
                msg_l = [
                    f"{date}: Sum of transfers on this day are non-zero",
                ]

                all_splits: list[tuple[str, Decimal, int]] = []
                for t_cat_id, splits in categories.items():
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
                    all_splits.extend(
                        (account, amount, t_cat_id) for account, amount in splits
                    )

                all_splits = sorted(
                    all_splits,
                    key=lambda item: (item[2], item[0], item[1]),
                )
                acct_len = max(len(item[0]) for item in all_splits)
                msg_l.extend(
                    f"  {acct:{acct_len}}: "
                    f"{utils.format_financial(amount, plus=True):>14} "
                    f"{cat_transfers_ids[t_cat_id]}"
                    for acct, amount, t_cat_id in all_splits
                )
                self._issues_raw[date_str] = "\n".join(msg_l)

            query = (
                s.query(TransactionSplit)
                .with_entities(
                    TransactionSplit.account_id,
                    TransactionSplit.date_ord,
                    TransactionSplit.amount,
                    TransactionSplit.category_id,
                )
                .where(TransactionSplit.category_id.in_(cat_transfers_ids))
                .order_by(TransactionSplit.date_ord)
            )
            current_date_ord: int | None = None
            total = {t_cat_id: Decimal(0) for t_cat_id in cat_transfers_ids}
            current_splits: dict[int, list[tuple[str, Decimal]]] = {
                t_cat_id: [] for t_cat_id in cat_transfers_ids
            }
            for acct_id, date_ord, amount, t_cat_id in query.yield_per(YIELD_PER):
                acct_id: int
                date_ord: int
                amount: Decimal
                if current_date_ord is None:
                    current_date_ord = date_ord
                if date_ord != current_date_ord:
                    if any(v != 0 for v in total.values()):
                        add_issue(current_date_ord, current_splits)
                    current_date_ord = date_ord
                    total = {t_cat_id: Decimal(0) for t_cat_id in cat_transfers_ids}
                    current_splits = {t_cat_id: [] for t_cat_id in cat_transfers_ids}

                total[t_cat_id] += amount
                current_splits[t_cat_id].append((accounts[acct_id], amount))

            if any(v != 0 for v in total.values()) and current_date_ord is not None:
                add_issue(current_date_ord, current_splits)

        self._commit_issues()
