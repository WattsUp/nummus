from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.models import Transaction

if TYPE_CHECKING:
    import datetime
    from decimal import Decimal

    from sqlalchemy import orm

    from nummus.models import Account
    from tests.conftest import RandomStringGenerator


def test_init_properties(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    rand_real: Decimal,
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "account_id": account.id_,
        "date": today,
        "amount": rand_real,
        "statement": rand_str_generator(),
        "payee": rand_str_generator(),
    }

    txn = Transaction(**d)
    session.add(txn)
    session.commit()

    assert txn.account_id == account.id_
    assert txn.date_ord == today.toordinal()
    assert txn.date == today
    assert txn.amount == d["amount"]
    assert txn.statement == d["statement"]
    assert txn.payee == d["payee"]
    assert not txn.cleared


@pytest.mark.parametrize(
    ("i", "target"),
    [
        (0, 1),
        (1, 0),
        (2, 0),
        (3, 4),
        (4, 3),
        (5, None),
        (6, None),
        (7, 0),
    ],
)
def test_find_similar(
    transactions_spending: list[Transaction],
    i: int,
    target: int | None,
) -> None:
    txn = transactions_spending[i]
    result = txn.find_similar()
    if target is None:
        assert result is None
    else:
        assert result == transactions_spending[target].id_
        assert txn.similar_txn_id == transactions_spending[target].id_


def test_find_similar_no_set(transactions_spending: list[Transaction]) -> None:
    txn = transactions_spending[0]
    result = txn.find_similar(set_property=False)
    assert result == transactions_spending[1].id_
    assert txn.similar_txn_id is None


def test_find_similar_cache(transactions_spending: list[Transaction]) -> None:
    txn = transactions_spending[0]
    result = txn.find_similar(set_property=True)
    assert result == transactions_spending[1].id_
    assert txn.similar_txn_id == transactions_spending[1].id_
    assert txn.find_similar(cache_ok=True) == transactions_spending[1].id_
