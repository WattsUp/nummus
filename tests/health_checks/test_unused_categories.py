from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.health_checks.unused_categories import UnusedCategories
from nummus.models import (
    HealthCheckIssue,
    query_count,
    TransactionCategory,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Transaction,
    )


def test_empty(session: orm.Session) -> None:
    # Mark all locked since those are excluded
    session.query(TransactionCategory).update({"locked": True})
    session.commit()

    c = UnusedCategories()
    c.test(session)
    assert c.issues == {}


def test_one(
    session: orm.Session,
    transactions: list[Transaction],
    categories: dict[str, int],
) -> None:
    _ = transactions
    # Mark all but groceries and other income locked since those are excluded
    session.query(TransactionCategory).where(
        TransactionCategory.name.not_in({"groceries", "other income"}),
    ).update({"locked": True})
    session.commit()

    c = UnusedCategories()
    c.test(session)
    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == TransactionCategory.id_to_uri(categories["groceries"])
    uri = i.uri

    target = "Groceries has no transactions nor budget assignments"
    assert c.issues == {uri: target}
