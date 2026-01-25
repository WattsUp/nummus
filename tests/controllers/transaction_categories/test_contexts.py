from __future__ import annotations

from nummus import sql
from nummus.controllers import base, transaction_categories
from nummus.models.transaction_category import (
    TransactionCategory,
    TransactionCategoryGroup,
)


def test_ctx() -> None:
    groups = transaction_categories.ctx_categories()

    exclude = {"securities traded"}

    for g in TransactionCategoryGroup:
        query = (
            TransactionCategory.query()
            .where(
                TransactionCategory.group == g,
                TransactionCategory.name.not_in(exclude),
            )
            .order_by(TransactionCategory.name)
        )
        target: list[base.NamePair] = [
            base.NamePair(t_cat.uri, t_cat.emoji_name) for t_cat in sql.yield_(query)
        ]
        assert groups[g] == target
