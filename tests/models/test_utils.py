from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from nummus.models import utils
from nummus.models.account import Account
from nummus.models.asset import (
    Asset,
    AssetCategory,
    AssetSplit,
    AssetValuation,
)
from nummus.models.transaction import Transaction, TransactionSplit

if TYPE_CHECKING:
    import datetime

    import sqlalchemy
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator


@pytest.fixture
def transactions(
    session: orm.Session,
    today: datetime.date,
    account: Account,
    categories: dict[str, int],
    rand_str_generator: RandomStringGenerator,
) -> list[Transaction]:
    for _ in range(10):
        txn = Transaction(
            account_id=account.id_,
            date=today,
            amount=100,
            statement=rand_str_generator(),
        )
        t_split = TransactionSplit(
            amount=100,
            parent=txn,
            category_id=categories["uncategorized"],
        )
        session.add_all((txn, t_split))
    session.commit()
    return Transaction.all()


@pytest.fixture
def valuations(
    today_ord: int,
    asset: Asset,
) -> list[AssetValuation]:
    a_id = asset.id_
    updates: dict[object, dict[str, object]] = {
        today_ord - 1: {"value": Decimal(10), "asset_id": a_id},
        today_ord: {"value": Decimal(100), "asset_id": a_id},
    }

    query = AssetValuation.query()
    utils.update_rows(AssetValuation, query, "date_ord", updates)
    return query.all()


def test_paginate_all(transactions: list[Transaction]) -> None:
    page, count, next_offset = utils.paginate(Transaction.query(), 50, 0)
    assert page == transactions
    assert count == len(transactions)
    assert next_offset is None


@pytest.mark.parametrize("offset", range(10))
def test_paginate_three(
    transactions: list[Transaction],
    offset: int,
) -> None:
    page, count, next_offset = utils.paginate(Transaction.query(), 3, offset)
    assert page == transactions[offset : offset + 3]
    assert count == len(transactions)
    if offset >= (len(transactions) - 3):
        assert next_offset is None
    else:
        assert next_offset == offset + 3


def test_paginate_three_page_1000(transactions: list[Transaction]) -> None:
    page, count, next_offset = utils.paginate(Transaction.query(), 3, 1000)
    assert page == []
    assert count == len(transactions)
    assert next_offset is None


def test_paginate_three_page_n1000(transactions: list[Transaction]) -> None:
    page, count, next_offset = utils.paginate(Transaction.query(), 3, -1000)
    assert page == transactions[0:3]
    assert count == len(transactions)
    assert next_offset == 3


def test_dump_table_configs() -> None:
    result = utils.dump_table_configs(Account)
    assert result[0] == "CREATE TABLE account ("
    assert result[-1] == ")"
    assert "\t" not in "\n".join(result)


def test_get_constraints() -> None:
    target = [
        (UniqueConstraint, "asset_id, date_ord"),
        (CheckConstraint, "multiplier > 0"),
        (ForeignKeyConstraint, "asset_id"),
    ]
    assert utils.get_constraints(AssetSplit) == target


def test_update_rows_new(
    today_ord: int,
    valuations: list[AssetValuation],
) -> None:
    assert utils.query_count(AssetValuation.query()) == len(valuations)

    v = AssetValuation.query().where(AssetValuation.date_ord == today_ord).one()
    assert v.value == Decimal(100)

    v = AssetValuation.query().where(AssetValuation.date_ord == (today_ord - 1)).one()
    assert v.value == Decimal(10)


def test_update_rows_edit(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    query = AssetValuation.query()
    updates: dict[object, dict[str, object]] = {
        today_ord - 2: {"value": Decimal(5), "asset_id": asset.id_},
        today_ord: {"value": Decimal(50), "asset_id": asset.id_},
    }
    utils.update_rows(AssetValuation, query, "date_ord", updates)
    assert utils.query_count(query) == len(valuations)

    v = query.where(AssetValuation.date_ord == today_ord).one()
    assert v.value == Decimal(50)

    v = query.where(AssetValuation.date_ord == (today_ord - 2)).one()
    assert v.value == Decimal(5)


def test_update_rows_delete(valuations: list[AssetValuation]) -> None:
    query = AssetValuation.query()
    utils.update_rows(AssetValuation, query, "date_ord", {})
    assert utils.query_count(query) == 0


def test_update_rows_list_edit(
    transactions: list[Transaction],
    categories: dict[str, int],
    rand_str_generator: RandomStringGenerator,
) -> None:
    txn = transactions[0]
    t_split_0 = txn.splits[0]
    new_split_amount = Decimal(20)
    memo_0 = rand_str_generator()
    memo_1 = rand_str_generator()
    updates: list[dict[str, object]] = [
        {
            "parent": txn,
            "category_id": categories["uncategorized"],
            "memo": memo_0,
            "amount": txn.amount - new_split_amount,
        },
        {
            "parent": txn,
            "category_id": categories["uncategorized"],
            "memo": memo_1,
            "amount": new_split_amount,
        },
    ]
    utils.update_rows_list(
        TransactionSplit,
        TransactionSplit.query().where(TransactionSplit.parent_id == txn.id_),
        updates,
    )
    assert t_split_0.parent_id == txn.id_
    assert t_split_0.memo == memo_0
    assert t_split_0.amount == txn.amount - new_split_amount

    t_split_1 = (
        TransactionSplit.query()
        .where(
            TransactionSplit.parent_id == txn.id_,
            TransactionSplit.id_ != t_split_0.id_,
        )
        .one()
    )
    assert t_split_1.parent_id == txn.id_
    assert t_split_1.memo == memo_1
    assert t_split_1.amount == new_split_amount


def test_update_rows_list_delete(
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    utils.update_rows_list(
        TransactionSplit,
        TransactionSplit.query().where(TransactionSplit.parent_id == txn.id_),
        [],
    )
    assert len(txn.splits) == 0


@pytest.mark.parametrize(
    ("where", "expect_asset"),
    [
        ([], False),
        ([Asset.category == AssetCategory.STOCKS], True),
        ([Asset.category == AssetCategory.BONDS], False),
    ],
)
def test_one_or_none(
    asset: Asset,
    where: list[sqlalchemy.ColumnClause],
    expect_asset: bool,
) -> None:
    query = Asset.query().where(*where)
    if expect_asset:
        assert utils.one_or_none(query) == asset
    else:
        assert utils.one_or_none(query) is None
