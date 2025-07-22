from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import transaction_categories
from nummus.models import TransactionCategory, TransactionCategoryGroup, YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_ctx(session: orm.Session) -> None:
    groups = transaction_categories.ctx_categories()

    exclude = {"securities traded"}

    for g in TransactionCategoryGroup:
        query = (
            session.query(TransactionCategory)
            .where(
                TransactionCategory.group == g,
                TransactionCategory.name.not_in(exclude),
            )
            .order_by(TransactionCategory.name)
        )
        target: list[transaction_categories.CategoryContext] = [
            {"name": t_cat.emoji_name, "uri": t_cat.uri}
            for t_cat in query.yield_per(YIELD_PER)
        ]
        assert groups[g] == target
