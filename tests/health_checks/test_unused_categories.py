from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.health_checks.unused_categories import UnusedCategories
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.transaction_category import TransactionCategory

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models.transaction import Transaction


def test_empty() -> None:
    # Mark all locked since those are excluded
    TransactionCategory.query().update({"locked": True})

    c = UnusedCategories()
    c.test()
    assert c.issues == {}


def test_one(
    session: orm.Session,
    transactions: list[Transaction],
    categories: dict[str, int],
) -> None:
    # Mark all but groceries and other income locked since those are excluded
    TransactionCategory.query().where(
        TransactionCategory.name.not_in({"groceries", "other income"}),
    ).update({"locked": True})

    c = UnusedCategories()
    c.test()
    assert HealthCheckIssue.count() == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == TransactionCategory.id_to_uri(categories["groceries"])
    uri = i.uri

    target = "Groceries has no transactions nor budget assignments"
    assert c.issues == {uri: target}
