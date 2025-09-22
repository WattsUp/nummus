"""Checks for split transactions with same payee and category."""

from __future__ import annotations

import datetime
from typing import NamedTuple, override, TYPE_CHECKING

from sqlalchemy import func

from nummus.health_checks.base import Base
from nummus.models import Account, TransactionCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


class RawIssue(NamedTuple):
    """Type definition for a raw issue."""

    uri: str
    source: str
    payee: str
    category: str


class UnnecessarySplits(Base):
    """Checks for split transactions with same payee and category."""

    _DESC = "Checks for split transactions with same payee and category."
    _SEVERE = False

    @override
    def test(self, s: orm.Session) -> None:
        accounts = Account.map_name(s)
        categories = TransactionCategory.map_name_emoji(s)

        issues: list[RawIssue] = []

        query = (
            s.query(TransactionSplit)
            .with_entities(
                TransactionSplit.date_ord,
                TransactionSplit.account_id,
                TransactionSplit.parent_id,
                TransactionSplit.payee,
                TransactionSplit.category_id,
            )
            .group_by(
                TransactionSplit.parent_id,
                TransactionSplit.category_id,
            )
            .order_by(TransactionSplit.date_ord)
            .having(func.count() > 1)
        )
        for date_ord, acct_id, t_id, payee, t_cat_id in query.yield_per(
            YIELD_PER,
        ):
            date_ord: int
            acct_id: int
            t_id: int
            payee: str | None
            t_cat_id: int
            # Create a robust uri for this duplicate
            uri = f"{t_id}.{payee}.{t_cat_id}"

            date = datetime.date.fromordinal(date_ord)
            source = f"{date} - {accounts[acct_id]}"
            issues.append(
                RawIssue(uri, source, payee or "", categories[t_cat_id]),
            )

        if len(issues) != 0:
            source_len = max(len(item.source) for item in issues)
            payee_len = max(len(item.payee) for item in issues)
            t_cat_len = max(len(item.category) for item in issues)
        else:
            source_len = 0
            payee_len = 0
            t_cat_len = 0

        self._commit_issues(
            s,
            {
                issue.uri: (
                    f"{issue.source:{source_len}}: "
                    f"{issue.payee:{payee_len}} - "
                    f"{issue.category:{t_cat_len}}"
                )
                for issue in issues
            },
        )
