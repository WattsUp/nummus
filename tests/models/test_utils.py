from __future__ import annotations

import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from nummus import exceptions as exc
from nummus import models
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSplit,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
    utils,
)
from nummus.models.asset import AssetValuation


def test_paginate() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    n_transactions = 10
    today = datetime.datetime.now().astimezone().date()

    # Create accounts
    acct = Account(
        name="Monkey Bank Checking",
        institution="Monkey Bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=False,
    )
    s.add(acct)
    s.commit()

    t_cat = TransactionCategory(
        emoji_name="Uncategorized",
        group=TransactionCategoryGroup.OTHER,
        locked=False,
        is_profit_loss=False,
        asset_linked=False,
        essential=False,
    )
    s.add(t_cat)
    s.commit()

    for _ in range(n_transactions):
        txn = Transaction(
            account_id=acct.id_,
            date=today,
            amount=100,
            statement=self.random_string(),
        )
        t_split = TransactionSplit(amount=100, parent=txn, category_id=t_cat.id_)
        s.add_all((txn, t_split))
    s.commit()

    query = s.query(Transaction)
    transactions = query.all()
    query = s.query(Transaction)

    page, count, next_offset = utils.paginate(query, 50, 0)  # type: ignore[attr-defined]
    assert page == transactions
    assert count == n_transactions
    self.assertIsNone(next_offset)

    page, count, next_offset = utils.paginate(query, 3, 0)  # type: ignore[attr-defined]
    assert page == transactions[0:3]
    assert count == n_transactions
    assert next_offset == 3

    page, count, next_offset = utils.paginate(query, 3, 3)  # type: ignore[attr-defined]
    assert page == transactions[3:6]
    assert count == n_transactions
    assert next_offset == 6

    page, count, next_offset = utils.paginate(query, 3, 6)  # type: ignore[attr-defined]
    assert page == transactions[6:9]
    assert count == n_transactions
    assert next_offset == 9

    page, count, next_offset = utils.paginate(query, 3, 9)  # type: ignore[attr-defined]
    assert page == transactions[9:]
    assert count == n_transactions
    self.assertIsNone(next_offset)

    page, count, next_offset = utils.paginate(query, 3, 1000)  # type: ignore[attr-defined]
    assert page == []
    assert count == n_transactions
    self.assertIsNone(next_offset)

    page, count, next_offset = utils.paginate(query, 3, -1000)  # type: ignore[attr-defined]
    assert page == transactions[0:3]
    assert count == n_transactions
    assert next_offset == 3


def test_dump_table_configs() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    result = utils.dump_table_configs(s, Account)
    assert result[0] == "CREATE TABLE account ("
    assert result[-1] == ")"
    self.assertNotIn("\t", "\n".join(result))


def test_get_constraints() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    target = [
        (UniqueConstraint, "asset_id, date_ord"),
        (CheckConstraint, "multiplier > 0"),
        (ForeignKeyConstraint, "asset_id"),
    ]
    result = utils.get_constraints(s, AssetSplit)
    assert result == target


def test_obj_session() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    # Create accounts
    acct = Account(
        name="Monkey Bank Checking",
        institution="Monkey Bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=False,
    )
    self.assertRaises(exc.UnboundExecutionError, utils.obj_session, acct)

    s.add(acct)
    s.commit()

    result = utils.obj_session(acct)
    assert result == s


def test_update_rows() -> None:
    s = self.get_session()
    models.metadata_create_all(s)
    today = datetime.datetime.now().astimezone().date()
    today_ord = today.toordinal()

    # Create asset
    a = Asset(
        name="Monkey Bank Checking",
        category=AssetCategory.CASH,
    )
    s.add(a)
    s.commit()
    a_id = a.id_

    updates: dict[object, dict[str, object]] = {
        today_ord - 1: {"value": Decimal(10), "asset_id": a_id},
        today_ord: {"value": Decimal(100), "asset_id": a_id},
    }

    query = s.query(AssetValuation)
    utils.update_rows(s, AssetValuation, query, "date_ord", updates)

    n = utils.query_count(query)
    assert n == 2

    v = query.where(AssetValuation.date_ord == today_ord).one()
    assert v.value == Decimal(100)

    v = query.where(AssetValuation.date_ord == (today_ord - 1)).one()
    assert v.value == Decimal(10)

    updates: dict[object, dict[str, object]] = {
        today_ord - 2: {"value": Decimal(5), "asset_id": a_id},
        today_ord: {"value": Decimal(50), "asset_id": a_id},
    }

    utils.update_rows(s, AssetValuation, query, "date_ord", updates)

    n = utils.query_count(query)
    assert n == 2

    v = query.where(AssetValuation.date_ord == today_ord).one()
    assert v.value == Decimal(50)

    v = query.where(AssetValuation.date_ord == (today_ord - 2)).one()
    assert v.value == Decimal(5)

    utils.update_rows(s, AssetValuation, query, "date_ord", {})
    n = utils.query_count(query)
    assert n == 0


def test_update_rows_list() -> None:
    s = self.get_session()
    models.metadata_create_all(s)
    today = datetime.datetime.now().astimezone().date()

    # Create account
    acct = Account(
        name="Monkey Bank Checking",
        institution="Monkey Bank",
        category=AccountCategory.CASH,
        closed=False,
        budgeted=False,
    )
    s.add(acct)
    s.commit()

    t_cat = TransactionCategory(
        emoji_name="Uncategorized",
        group=TransactionCategoryGroup.OTHER,
        locked=False,
        is_profit_loss=False,
        asset_linked=False,
        essential=False,
    )
    s.add(t_cat)
    s.commit()

    txn = Transaction(
        account_id=acct.id_,
        date=today,
        amount=100,
        statement=self.random_string(),
    )
    t_split_0 = TransactionSplit(amount=100, parent=txn, category_id=t_cat.id_)
    s.add_all((txn, t_split_0))
    s.commit()

    new_split_amount = Decimal(20)
    memo_0 = self.random_string()
    memo_1 = self.random_string()
    tag_0 = self.random_string()
    tag_1 = self.random_string()
    updates: list[dict[str, object]] = [
        {
            "parent": txn,
            "category_id": t_cat.id_,
            "memo": memo_0,
            "tag": tag_0,
            "amount": txn.amount - new_split_amount,
        },
        {
            "parent": txn,
            "category_id": t_cat.id_,
            "memo": memo_1,
            "tag": tag_1,
            "amount": new_split_amount,
        },
    ]
    utils.update_rows_list(s, TransactionSplit, s.query(TransactionSplit), updates)
    s.commit()
    assert t_split_0.parent_id == txn.id_
    assert t_split_0.memo == memo_0
    assert t_split_0.tag == tag_0
    assert t_split_0.amount == txn.amount - new_split_amount

    t_split_1 = (
        s.query(TransactionSplit).where(TransactionSplit.id_ != t_split_0.id_).one()
    )
    assert t_split_1.parent_id == txn.id_
    assert t_split_1.memo == memo_1
    assert t_split_1.tag == tag_1
    assert t_split_1.amount == new_split_amount

    updates: list[dict[str, object]] = [
        {
            "parent": txn,
            "category_id": t_cat.id_,
            "memo": memo_0,
            "tag": tag_0,
            "amount": txn.amount,
        },
    ]
    utils.update_rows_list(s, TransactionSplit, s.query(TransactionSplit), updates)
    s.commit()
    assert t_split_0.parent_id == txn.id_
    assert t_split_0.memo == memo_0
    assert t_split_0.tag == tag_0
    assert t_split_0.amount == txn.amount

    t_split_1 = (
        s.query(TransactionSplit)
        .where(TransactionSplit.id_ != t_split_0.id_)
        .one_or_none()
    )
    self.assertIsNone(t_split_1)


def test_one_or_none() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    # Create asset
    a_0 = Asset(
        name="Monkey Bank Cash",
        category=AssetCategory.CASH,
    )
    s.add(a_0)
    a_1 = Asset(
        name="Monkey Bank Crypto",
        category=AssetCategory.CRYPTOCURRENCY,
    )
    s.add(a_1)

    # Too many matches
    result = utils.one_or_none(s.query(Asset))
    self.assertIsNone(result)

    # One matches
    result = utils.one_or_none(
        s.query(Asset).where(Asset.category == AssetCategory.CASH),
    )
    assert result == a_0

    # No matches
    result = utils.one_or_none(
        s.query(Asset).where(Asset.category == AssetCategory.BONDS),
    )
    self.assertIsNone(result)
