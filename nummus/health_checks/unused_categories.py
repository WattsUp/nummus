"""Checks for categories without transactions or budget assignment."""

from __future__ import annotations

from typing_extensions import override

from nummus.health_checks.base import Base
from nummus.models import BudgetAssignment, TransactionCategory, TransactionSplit


class UnusedCategories(Base):
    """Checks for categories without transactions or budget assignment."""

    _DESC = "Checks for categories without transactions or budget assignments."
    _SEVERE = False

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            # Only check unlocked categories
            query = (
                s.query(TransactionCategory)
                .with_entities(TransactionCategory.id_, TransactionCategory.emoji_name)
                .where(TransactionCategory.locked.is_(False))
            )
            categories: dict[int, str] = dict(query.all())  # type: ignore[attr-defined]
            if len(categories) == 0:
                self._commit_issues()
                return
            category_len = max(len(name) for name in categories.values())

            query = s.query(TransactionSplit.category_id)
            used_categories = {r[0] for r in query.distinct()}

            query = s.query(BudgetAssignment.category_id)
            used_categories.update(r[0] for r in query.distinct())
            for t_cat_id, name in categories.items():
                if t_cat_id in used_categories:
                    continue
                uri = TransactionCategory.id_to_uri(t_cat_id)
                msg = (
                    f"{name:{category_len}} has no transactions or "
                    "no budget assignments"
                )
                self._issues_raw[uri] = msg

        self._commit_issues()
