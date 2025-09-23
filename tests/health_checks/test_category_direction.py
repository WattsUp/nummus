from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import utils
from nummus.health_checks.category_direction import CategoryDirection
from nummus.models import (
    HealthCheckIssue,
    query_count,
    Transaction,
    TransactionSplit,
)

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import (
        Account,
    )


def test_empty(session: orm.Session) -> None:
    c = CategoryDirection()
    c.test(session)
    assert c.issues == {}


@pytest.mark.parametrize(
    ("category", "category_name", "amount"),
    [
        ("other income", "Other Income", Decimal(-10)),
        ("groceries", "Groceries", Decimal(10)),
    ],
)
def test_check(
    today: datetime.date,
    session: orm.Session,
    categories: dict[str, int],
    account: Account,
    category: str,
    category_name: str,
    amount: Decimal,
    rand_str: str,
) -> None:
    txn = Transaction(
        account_id=account.id_,
        date=today,
        amount=amount,
        statement=rand_str,
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories[category],
    )
    session.add_all((txn, t_split))
    session.commit()
    t_uri = t_split.uri

    c = CategoryDirection()
    c.test(session)

    assert query_count(session.query(HealthCheckIssue)) == 1

    i = session.query(HealthCheckIssue).one()
    assert i.check == c.name()
    assert i.value == t_uri
    uri = i.uri

    if amount < 0:
        target = (
            f"{today} - Monkey bank checking: {utils.format_financial(amount)} "
            f"to [blank] has negative amount with income category {category_name}"
        )
    else:
        target = (
            f"{today} - Monkey bank checking: {utils.format_financial(amount)} "
            f"to [blank] has positive amount with expense category {category_name}"
        )
    assert c.issues == {uri: target}
