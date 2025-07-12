"""Checks for split transactions with same payee, category, and tag."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import func
from typing_extensions import override

from nummus.health_checks.base import Base
from nummus.models import Account, TransactionCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


class UnnecessarySplits(Base):
    """Checks for split transactions with same payee, category, and tag."""

    _DESC = "Checks for split transactions with same payee, category, and tag."
    _SEVERE = False

    @override
    def test(self, s: orm.Session) -> None:
        accounts = Account.map_name(s)
        categories = TransactionCategory.map_name_emoji(s)

        issues: list[tuple[str, str, str, str, str]] = []

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.account_id,
                TransactionSplit.parent_id,
                TransactionSplit.payee,
                TransactionSplit.category_id,
                TransactionSplit.tag,
            )
            .group_by(
                TransactionSplit.parent_id,
                TransactionSplit.category_id,
                TransactionSplit.tag,
            )
            .order_by(TransactionSplit.date_ord)
            .having(func.count() > 1)
        )
        for date_ord, acct_id, t_id, payee, t_cat_id, tag in query.yield_per(
            YIELD_PER,
        ):
            date_ord: int
            acct_id: int
            t_id: int
            payee: str | None
            t_cat_id: int
            tag: str | None
            # Create a robust uri for this duplicate
            uri = f"{t_id}.{payee}.{t_cat_id}.{tag}"

            date = datetime.date.fromordinal(date_ord)
            source = f"{date} - {accounts[acct_id]}"
            issues.append(
                (uri, source, payee or "", categories[t_cat_id], tag or ""),
            )

        if len(issues) != 0:
            source_len = max(len(item[1]) for item in issues)
            payee_len = max(len(item[2]) for item in issues)
            t_cat_len = max(len(item[3]) for item in issues)
            tag_len = max(len(item[4]) for item in issues)
        else:
            source_len = 0
            payee_len = 0
            t_cat_len = 0
            tag_len = 0

        self._commit_issues(
            s,
            {
                uri: (
                    f"{source:{source_len}}: "
                    f"{payee:{payee_len}} - "
                    f"{t_cat:{t_cat_len}} - "
                    f"{tag:{tag_len}}"
                )
                for uri, source, payee, t_cat, tag in issues
            },
        )
