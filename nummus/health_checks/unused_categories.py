"""Checks for categories without transactions or budget assignment."""

from __future__ import annotations

from typing import override

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.models.budget import BudgetAssignment
from nummus.models.transaction import TransactionSplit
from nummus.models.transaction_category import TransactionCategory


class UnusedCategories(HealthCheck):
    """Checks for categories without transactions or budget assignment."""

    _DESC = "Checks for categories without transactions or budget assignments."
    _SEVERE = False

    @override
    def test(self) -> None:
        # Only check unlocked categories
        query = TransactionCategory.query(
            TransactionCategory.id_,
            TransactionCategory.emoji_name,
        ).where(TransactionCategory.locked.is_(False))
        categories: dict[int, str] = sql.to_dict(query)
        if len(categories) == 0:
            self._commit_issues({})
            return

        query = TransactionSplit.query(TransactionSplit.category_id)
        used_categories = set(sql.col0(query))

        query = BudgetAssignment.query(BudgetAssignment.category_id)
        used_categories.update(sql.col0(query))

        categories = {
            t_cat_id: name
            for t_cat_id, name in categories.items()
            if t_cat_id not in used_categories
        }
        category_len = (
            max(len(name) for name in categories.values()) if categories else 0
        )

        self._commit_issues(
            {
                TransactionCategory.id_to_uri(t_cat_id): (
                    f"{name:{category_len}} has no "
                    "transactions nor budget assignments"
                )
                for t_cat_id, name in categories.items()
            },
        )
