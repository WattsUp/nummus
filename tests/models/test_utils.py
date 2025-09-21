from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from nummus import exceptions as exc
from nummus.models import (
    Account,
    Asset,
    AssetCategory,
    AssetSplit,
    AssetValuation,
    Transaction,
    TransactionSplit,
    utils,
)

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
    return session.query(Transaction).all()


@pytest.fixture
def valuations(
    session: orm.Session,
    today_ord: int,
    asset: Asset,
) -> list[AssetValuation]:
    a_id = asset.id_
    updates: dict[object, dict[str, object]] = {
        today_ord - 1: {"value": Decimal(10), "asset_id": a_id},
        today_ord: {"value": Decimal(100), "asset_id": a_id},
    }

    query = session.query(AssetValuation)
    utils.update_rows(session, AssetValuation, query, "date_ord", updates)
    session.commit()
    return query.all()


def test_paginate_all(session: orm.Session, transactions: list[Transaction]) -> None:
    page, count, next_offset = utils.paginate(session.query(Transaction), 50, 0)
    assert page == transactions
    assert count == len(transactions)
    assert next_offset is None


@pytest.mark.parametrize("offset", range(10))
def test_paginate_three(
    session: orm.Session,
    transactions: list[Transaction],
    offset: int,
) -> None:
    page, count, next_offset = utils.paginate(session.query(Transaction), 3, offset)
    assert page == transactions[offset : offset + 3]
    assert count == len(transactions)
    if offset >= (len(transactions) - 3):
        assert next_offset is None
    else:
        assert next_offset == offset + 3


def test_paginate_three_page_1000(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    page, count, next_offset = utils.paginate(session.query(Transaction), 3, 1000)
    assert page == []
    assert count == len(transactions)
    assert next_offset is None


def test_paginate_three_page_n1000(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    page, count, next_offset = utils.paginate(session.query(Transaction), 3, -1000)
    assert page == transactions[0:3]
    assert count == len(transactions)
    assert next_offset == 3


def test_dump_table_configs(session: orm.Session) -> None:
    result = utils.dump_table_configs(session, Account)
    assert result[0] == "CREATE TABLE account ("
    assert result[-1] == ")"
    assert "\t" not in "\n".join(result)


def test_get_constraints(session: orm.Session) -> None:
    target = [
        (UniqueConstraint, "asset_id, date_ord"),
        (CheckConstraint, "multiplier > 0"),
        (ForeignKeyConstraint, "asset_id"),
    ]
    assert utils.get_constraints(session, AssetSplit) == target


def test_obj_session(session: orm.Session, account: Account) -> None:
    result = utils.obj_session(account)
    assert result == session


def test_obj_session_detached() -> None:
    acct = Account()
    with pytest.raises(exc.UnboundExecutionError):
        utils.obj_session(acct)


def test_update_rows_new(
    session: orm.Session,
    today_ord: int,
    valuations: list[AssetValuation],
) -> None:
    query = session.query(AssetValuation)
    assert utils.query_count(query) == len(valuations)

    v = query.where(AssetValuation.date_ord == today_ord).one()
    assert v.value == Decimal(100)

    v = query.where(AssetValuation.date_ord == (today_ord - 1)).one()
    assert v.value == Decimal(10)


def test_update_rows_edit(
    session: orm.Session,
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    query = session.query(AssetValuation)
    updates: dict[object, dict[str, object]] = {
        today_ord - 2: {"value": Decimal(5), "asset_id": asset.id_},
        today_ord: {"value": Decimal(50), "asset_id": asset.id_},
    }
    utils.update_rows(session, AssetValuation, query, "date_ord", updates)
    session.commit()
    assert utils.query_count(query) == len(valuations)

    v = query.where(AssetValuation.date_ord == today_ord).one()
    assert v.value == Decimal(50)

    v = query.where(AssetValuation.date_ord == (today_ord - 2)).one()
    assert v.value == Decimal(5)


def test_update_rows_delete(
    session: orm.Session,
    valuations: list[AssetValuation],
) -> None:
    _ = valuations
    query = session.query(AssetValuation)
    utils.update_rows(session, AssetValuation, query, "date_ord", {})
    assert utils.query_count(query) == 0


def test_update_rows_list_edit(
    session: orm.Session,
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
        session,
        TransactionSplit,
        session.query(TransactionSplit).where(TransactionSplit.parent_id == txn.id_),
        updates,
    )
    session.commit()
    assert t_split_0.parent_id == txn.id_
    assert t_split_0.memo == memo_0
    assert t_split_0.amount == txn.amount - new_split_amount

    t_split_1 = (
        session.query(TransactionSplit)
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
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    txn = transactions[0]
    utils.update_rows_list(
        session,
        TransactionSplit,
        session.query(TransactionSplit).where(TransactionSplit.parent_id == txn.id_),
        [],
    )
    session.commit()
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
    session: orm.Session,
    asset: Asset,
    where: list[sqlalchemy.ColumnClause],
    expect_asset: bool,
) -> None:
    _ = asset
    query = session.query(Asset).where(*where)
    if expect_asset:
        assert utils.one_or_none(query) == asset
    else:
        assert utils.one_or_none(query) is None
