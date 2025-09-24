"""Checks for non-zero net transfers."""

from __future__ import annotations

import datetime
import operator
import textwrap
from collections import defaultdict
from decimal import Decimal
from typing import override, TYPE_CHECKING

from nummus import utils
from nummus.health_checks.base import Base
from nummus.models import (
    Account,
    query_to_dict,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    YIELD_PER,
)

if TYPE_CHECKING:
    from sqlalchemy import orm


class UnbalancedTransfers(Base):
    """Checks for non-zero net transfers."""

    _DESC = textwrap.dedent(
        """\
        Transfers move money between accounts so none should be lost.
        If there are transfer fees, add that as a separate transaction.""",
    )
    _SEVERE = True

    @override
    def test(self, s: orm.Session) -> None:
        issues: dict[str, str] = {}
        query = s.query(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
        ).where(
            TransactionCategory.group == TransactionCategoryGroup.TRANSFER,
        )
        cat_transfers_ids: dict[int, str] = query_to_dict(query)

        accounts = Account.map_name(s)

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.account_id,
                TransactionSplit.date_ord,
                TransactionSplit.amount,
                TransactionSplit.category_id,
            )
            .where(TransactionSplit.category_id.in_(cat_transfers_ids))
            .order_by(TransactionSplit.date_ord, TransactionSplit.amount)
        )
        current_date_ord: int | None = None
        total = defaultdict(Decimal)
        current_splits: dict[int, list[tuple[str, Decimal]]] = defaultdict(list)
        for acct_id, date_ord, amount, t_cat_id in query.yield_per(YIELD_PER):
            acct_id: int
            date_ord: int
            amount: Decimal
            if current_date_ord is None:
                current_date_ord = date_ord
            if date_ord != current_date_ord:
                if any(v != 0 for v in total.values()):
                    uri, msg = self._create_issue(
                        current_date_ord,
                        current_splits,
                        cat_transfers_ids,
                    )
                    issues[uri] = msg
                current_date_ord = date_ord
                total = defaultdict(Decimal)
                current_splits = defaultdict(list)

            total[t_cat_id] += amount
            current_splits[t_cat_id].append((accounts[acct_id], amount))

        if any(v != 0 for v in total.values()) and current_date_ord is not None:
            uri, msg = self._create_issue(
                current_date_ord,
                current_splits,
                cat_transfers_ids,
            )
            issues[uri] = msg

        self._commit_issues(s, issues)

    @classmethod
    def _create_issue(
        cls,
        date_ord: int,
        categories: dict[int, list[tuple[str, Decimal]]],
        cat_transfers_ids: dict[int, str],
    ) -> tuple[str, str]:
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
            all_splits.extend((account, amount, t_cat_id) for account, amount in splits)

        all_splits = sorted(all_splits, key=operator.itemgetter(2, 0, 1))
        acct_len = max(len(item[0]) for item in all_splits)
        msg_l.extend(
            f"  {acct:{acct_len}}: "
            f"{utils.format_financial(amount, plus=True):>14} "
            f"{cat_transfers_ids[t_cat_id]}"
            for acct, amount, t_cat_id in all_splits
        )
        return date_str, "\n".join(msg_l)
