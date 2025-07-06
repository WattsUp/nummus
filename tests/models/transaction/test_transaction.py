from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus.models import Account, Asset, Transaction, TransactionSplit

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

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


@pytest.fixture
def transactions(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    account_savings: Account,
    asset: Asset,
    categories: dict[str, int],
) -> list[Transaction]:
    statement_income = rand_str_generator()
    statement_groceries = rand_str_generator()
    statement_rent = rand_str_generator()
    specs = [
        (account, Decimal(100), statement_income, "other income"),
        (account, Decimal(100), statement_income, "other income"),
        (account, Decimal(120), statement_income, "other income"),
        (account, Decimal(-10), statement_groceries, "groceries"),
        (account, Decimal(-10), statement_groceries + " other word", "groceries"),
        (account, Decimal(-50), statement_rent, "rent"),
        (account, Decimal(1000), rand_str_generator(), "other income"),
        (account_savings, Decimal(100), statement_income, "other income"),
    ]
    for acct, amount, statement, category in specs:
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=amount,
            statement=statement,
        )
        t_split = TransactionSplit(
            parent=txn,
            amount=txn.amount,
            category_id=categories[category],
        )
        session.add_all((txn, t_split))

    txn = Transaction(
        account_id=account.id_,
        date=today,
        amount=-50,
        statement=statement_rent + " other word",
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=10,
        category_id=categories["securities traded"],
    )
    session.add_all((txn, t_split))

    session.commit()
    return session.query(Transaction).all()


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
    transactions: list[Transaction],
    i: int,
    target: int | None,
) -> None:
    txn = transactions[i]
    result = txn.find_similar()
    if target is None:
        assert result is None
    else:
        assert result == transactions[target].id_
        assert txn.similar_txn_id == transactions[target].id_


def test_find_similar_no_set(transactions: list[Transaction]) -> None:
    txn = transactions[0]
    result = txn.find_similar(set_property=False)
    assert result == transactions[1].id_
    assert txn.similar_txn_id is None


def test_find_similar_cache(transactions: list[Transaction]) -> None:
    txn = transactions[0]
    result = txn.find_similar(set_property=True)
    assert result == transactions[1].id_
    assert txn.similar_txn_id == transactions[1].id_
    assert txn.find_similar(cache_ok=True) == transactions[1].id_
