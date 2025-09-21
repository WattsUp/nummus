from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from nummus.models import Transaction, TransactionSplit

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Account, Asset
    from tests.conftest import RandomStringGenerator


@pytest.fixture
def transactions(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    asset: Asset,
    categories: dict[str, int],
    transactions: list[Transaction],
) -> list[Transaction]:
    _ = transactions
    # Add dividends yesterday
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=1),
        amount=0,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split_0 = TransactionSplit(
        parent=txn,
        amount=-1,
        asset_id=asset.id_,
        asset_quantity_unadjusted=1,
        category_id=categories["securities traded"],
    )
    t_split_1 = TransactionSplit(
        parent=txn,
        amount=1,
        asset_id=asset.id_,
        asset_quantity_unadjusted=0,
        category_id=categories["dividends received"],
    )
    session.add_all((txn, t_split_0, t_split_1))

    # Add fee today
    txn = Transaction(
        account_id=account.id_,
        date=today,
        amount=0,
        statement=rand_str_generator(),
        payee="Monkey Bank",
        cleared=True,
    )
    t_split_0 = TransactionSplit(
        parent=txn,
        amount=2,
        asset_id=asset.id_,
        asset_quantity_unadjusted=-2,
        category_id=categories["securities traded"],
    )
    t_split_1 = TransactionSplit(
        parent=txn,
        amount=-2,
        asset_id=asset.id_,
        asset_quantity_unadjusted=0,
        category_id=categories["investment fees"],
    )
    session.add_all((txn, t_split_0, t_split_1))

    session.commit()
    return session.query(Transaction).order_by(Transaction.date_ord).all()
