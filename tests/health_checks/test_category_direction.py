from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import sql
from nummus.health_checks.category_direction import CategoryDirection
from nummus.models.currency import CURRENCY_FORMATS, DEFAULT_CURRENCY
from nummus.models.health_checks import HealthCheckIssue
from nummus.models.transaction import Transaction, TransactionSplit

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models.account import Account


def test_empty() -> None:
    c = CategoryDirection()
    c.test()
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
    with session.begin_nested():
        txn = Transaction.create(
            account_id=account.id_,
            date=today,
            amount=amount,
            statement=rand_str,
        )
        t_split = TransactionSplit.create(
            parent=txn,
            amount=txn.amount,
            category_id=categories[category],
        )
    t_uri = t_split.uri

    c = CategoryDirection()
    c.test()

    assert sql.count(HealthCheckIssue.query()) == 1

    i = HealthCheckIssue.one()
    assert i.check == c.name()
    assert i.value == t_uri
    uri = i.uri

    cf = CURRENCY_FORMATS[DEFAULT_CURRENCY]
    if amount < 0:
        target = (
            f"{today} - Monkey bank checking: {cf(amount)} "
            f"to [blank] has negative amount with income category {category_name}"
        )
    else:
        target = (
            f"{today} - Monkey bank checking: {cf(amount)} "
            f"to [blank] has positive amount with expense category {category_name}"
        )
    assert c.issues == {uri: target}
