"""Checks for categories without transactions or budget assignment."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.health_checks.base import Base
from nummus.models import (
    BudgetAssignment,
    query_to_dict,
    TransactionCategory,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm


class UnusedCategories(Base):
    """Checks for categories without transactions or budget assignment."""

    _DESC = "Checks for categories without transactions or budget assignments."
    _SEVERE = False

    @override
    def test(self, s: orm.Session) -> None:
        # Only check unlocked categories
        query = (
            s.query(TransactionCategory)
            .with_entities(TransactionCategory.id_, TransactionCategory.emoji_name)
            .where(TransactionCategory.locked.is_(False))
        )
        categories: dict[int, str] = query_to_dict(query)
        if len(categories) == 0:
            self._commit_issues(s, {})
            return

        query = s.query(TransactionSplit.category_id)
        used_categories = {r[0] for r in query.distinct()}

        query = s.query(BudgetAssignment.category_id)
        used_categories.update(r[0] for r in query.distinct())

        categories = {
            t_cat_id: name
            for t_cat_id, name in categories.items()
            if t_cat_id not in used_categories
        }
        category_len = (
            max(len(name) for name in categories.values()) if categories else 0
        )

        self._commit_issues(
            s,
            {
                TransactionCategory.id_to_uri(t_cat_id): (
                    f"{name:{category_len}} has no "
                    "transactions nor budget assignments"
                )
                for t_cat_id, name in categories.items()
            },
        )
