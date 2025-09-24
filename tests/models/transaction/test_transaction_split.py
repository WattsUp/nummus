from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import Transaction, TransactionSplit
from tests import conftest

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import Account, Asset
    from tests.conftest import RandomRealGenerator, RandomStringGenerator


def test_init_properties(
    today: datetime.date,
    session: orm.Session,
    account: Account,
    asset: Asset,
    categories: dict[str, int],
    rand_real_generator: RandomRealGenerator,
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "account_id": account.id_,
        "date": today,
        "amount": rand_real_generator(),
        "statement": rand_str_generator(),
        "payee": rand_str_generator(),
    }

    txn = Transaction(**d)
    session.add(txn)
    session.commit()

    d = {
        "amount": d["amount"],
        "parent": txn,
        "category_id": categories["transfers"],
        "asset_id": asset.id_,
        "asset_quantity_unadjusted": rand_real_generator(),
        "memo": rand_str_generator(),
    }

    t_split_0 = TransactionSplit(**d)

    session.add(t_split_0)
    session.commit()
    assert t_split_0.parent == txn
    assert t_split_0.parent_id == txn.id_
    assert t_split_0.category_id == d["category_id"]
    assert t_split_0.asset_id == d["asset_id"]
    assert t_split_0.asset_quantity_unadjusted == d["asset_quantity_unadjusted"]
    assert t_split_0.asset_quantity == d["asset_quantity_unadjusted"]
    assert t_split_0.amount == d["amount"]
    assert t_split_0.date_ord == txn.date_ord
    assert t_split_0.date == txn.date
    assert t_split_0.payee == txn.payee
    assert t_split_0.cleared == txn.cleared
    assert t_split_0.account_id == account.id_
    target = f"{txn.payee} {t_split_0.memo}".lower()
    assert t_split_0.text_fields == target


def test_zero_amount(session: orm.Session, transactions: list[Transaction]) -> None:
    t_split = transactions[1].splits[0]
    t_split.amount = Decimal()
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        TransactionSplit(memo="a")


def test_parent_attributes_direct(transactions: list[Transaction]) -> None:
    t_split = transactions[1].splits[0]
    with pytest.raises(exc.ParentAttributeError):
        t_split.parent_id = 0


def test_asset_quantity_direct(transactions: list[Transaction]) -> None:
    t_split = transactions[1].splits[0]
    with pytest.raises(exc.ComputedColumnError):
        t_split.asset_quantity = Decimal()


def test_text_fields_direct(transactions: list[Transaction]) -> None:
    t_split = transactions[1].splits[0]
    with pytest.raises(exc.ComputedColumnError):
        t_split.text_fields = None


def test_unset_asset_quantity(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    t_split = transactions[1].splits[0]
    t_split._asset_qty_unadjusted = None
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_clear_asset_quantity(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    t_split = transactions[1].splits[0]
    t_split.asset_quantity_unadjusted = None
    session.commit()
    assert t_split.asset_quantity is None


def test_adjust_asset_quantity_none(transactions: list[Transaction]) -> None:
    t_split = transactions[0].splits[0]
    with pytest.raises(exc.NonAssetTransactionError):
        t_split.adjust_asset_quantity(Decimal(1))


def test_adjust_asset_quantity(
    transactions: list[Transaction],
    rand_real: Decimal,
) -> None:
    t_split = transactions[1].splits[0]
    t_split.adjust_asset_quantity(rand_real)
    assert (
        t_split.asset_quantity == (t_split.asset_quantity_unadjusted or 0) * rand_real
    )


def test_adjust_asset_quantity_residual_none(transactions: list[Transaction]) -> None:
    t_split = transactions[0].splits[0]
    with pytest.raises(exc.NonAssetTransactionError):
        t_split.adjust_asset_quantity_residual(Decimal(1))


def test_adjust_asset_quantity_residual(
    transactions: list[Transaction],
    rand_real: Decimal,
) -> None:
    t_split = transactions[1].splits[0]
    t_split.adjust_asset_quantity_residual(rand_real)
    assert (
        t_split.asset_quantity == (t_split.asset_quantity_unadjusted or 0) - rand_real
    )


def test_parent(transactions: list[Transaction]) -> None:
    txn = transactions[0]
    t_split = txn.splits[0]
    assert t_split.parent == txn


def test_search_none(session: orm.Session, transactions: list[Transaction]) -> None:
    _ = transactions
    query = session.query(TransactionSplit)
    with pytest.raises(exc.EmptySearchError):
        TransactionSplit.search(query, "")


@pytest.mark.parametrize(
    ("search_str", "target"),
    [
        ("other income", [0]),
        ("engineer other income", [0, 1]),
        ('engineer +"other income"', [0]),
        ("+engineer", [1, 0]),  # same qty so sort by newest first
        ("-engineer", [3, 2]),  # same qty so sort by newest first
        ("engineer -other", [1]),
        ("rent", [3, 2]),  # same qty so sort by newest first
        ("rent transfer", [3, 2]),
        ('"rent transfer"', [3]),
        ("+fake", []),
    ],
    ids=conftest.id_func,
)
def test_search(
    session: orm.Session,
    transactions: list[Transaction],
    search_str: str,
    target: list[int],
) -> None:
    query = session.query(TransactionSplit)
    result = TransactionSplit.search(query, search_str)
    assert result == [transactions[i].splits[0].id_ for i in target]
