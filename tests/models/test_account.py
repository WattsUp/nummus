from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetValuation,
    Transaction,
    TransactionSplit,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.conftest import RandomStringGenerator


@pytest.fixture
def transactions(
    today: datetime.date,
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
    account: Account,
    asset: Asset,
    categories: dict[str, int],
) -> list[Transaction]:
    # Fund account on 3 days before today
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=3),
        amount=100,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        category_id=categories["other income"],
    )
    session.add_all((txn, t_split))

    # Buy asset on 2 days before today
    txn = Transaction(
        account_id=account.id_,
        date=today - datetime.timedelta(days=2),
        amount=-10,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=10,
        category_id=categories["securities traded"],
    )
    session.add_all((txn, t_split))

    # Sell asset tomorrow
    txn = Transaction(
        account_id=account.id_,
        date=today + datetime.timedelta(days=1),
        amount=50,
        statement=rand_str_generator(),
    )
    t_split = TransactionSplit(
        parent=txn,
        amount=txn.amount,
        asset_id=asset.id_,
        asset_quantity_unadjusted=-5,
        category_id=categories["securities traded"],
    )
    session.add_all((txn, t_split))

    session.commit()
    return session.query(Transaction).all()


def test_init_properties(
    rand_str_generator: RandomStringGenerator,
    session: orm.Session,
) -> None:
    d = {
        "name": rand_str_generator(),
        "institution": rand_str_generator(),
        "category": AccountCategory.CASH,
        "closed": False,
        "budgeted": False,
    }
    acct = Account(**d)

    session.add(acct)
    session.commit()

    assert acct.name == d["name"]
    assert acct.institution == d["institution"]
    assert acct.category == d["category"]
    assert acct.closed == d["closed"]
    assert acct.opened_on_ord is None
    assert acct.updated_on_ord is None


def test_short(account: Account) -> None:
    with pytest.raises(exc.InvalidORMValueError):
        account.name = "a"


def test_ids(session: orm.Session, account: Account) -> None:
    ids = Account.ids(session, AccountCategory.CASH)
    assert ids == {account.id_}


def test_ids_none(session: orm.Session, account: Account) -> None:
    _ = account
    ids = Account.ids(session, AccountCategory.CREDIT)
    assert ids == set()


def test_date_properties(
    today_ord: int,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    assert account.opened_on_ord == today_ord - 3
    assert account.updated_on_ord == today_ord + 1


def test_get_asset_qty_empty(
    today_ord: int,
    session: orm.Session,
    account: Account,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = account.get_asset_qty(start_ord, end_ord)
    assert result == {}
    # defaultdict is correct length
    assert result[0] == [Decimal(0)] * 7

    result = Account.get_asset_qty_all(session, start_ord, end_ord)
    assert result == {}


def test_get_asset_qty(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result_qty = account.get_asset_qty(start_ord, end_ord)
    target = {
        asset.id_: [
            Decimal(0),
            Decimal(10),
            Decimal(10),
            Decimal(10),
            Decimal(5),
            Decimal(5),
            Decimal(5),
        ],
    }
    assert result_qty == target


def test_get_asset_qty_today(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result_qty = account.get_asset_qty(today_ord, today_ord)
    assert result_qty == {asset.id_: [Decimal(10)]}


def test_get_value_empty(
    today_ord: int,
    session: orm.Session,
    account: Account,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    values, profits, assets = account.get_value(start_ord, end_ord)
    assert values == [Decimal(0)] * 7
    assert profits == [Decimal(0)] * 7
    assert assets == {}
    # defaultdict is correct length
    assert assets[0] == [Decimal(0)] * 7

    values, profits, assets = Account.get_value_all(session, start_ord, end_ord)
    assert values == {}
    assert profits == {}
    assert assets == {}


def test_get_value(
    today_ord: int,
    account: Account,
    asset: Asset,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    _ = asset_valuation
    start_ord = today_ord - 4
    end_ord = today_ord + 3
    values, profits, assets = account.get_value(start_ord, end_ord)
    target = [
        Decimal(0),
        Decimal(100),
        Decimal(90),
        Decimal(90),
        Decimal(190),
        Decimal(190),
        Decimal(190),
        Decimal(190),
    ]
    assert values == target
    target = [
        Decimal(0),
        Decimal(0),
        Decimal(-10),
        Decimal(-10),
        Decimal(90),
        Decimal(90),
        Decimal(90),
        Decimal(90),
    ]
    assert profits == target
    target = {
        asset.id_: [
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(100),
            Decimal(50),
            Decimal(50),
            Decimal(50),
        ],
    }
    assert assets == target


def test_get_value_today(
    today_ord: int,
    account: Account,
    asset: Asset,
    asset_valuation: AssetValuation,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    _ = asset_valuation
    values, profits, assets = account.get_value(today_ord, today_ord)
    assert values == [Decimal(190)]
    assert profits == [Decimal(0)]
    assert assets == {asset.id_: [Decimal(100)]}


def test_get_value_buy_day(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    values, profits, assets = account.get_value(today_ord - 2, today_ord - 2)
    assert values == [Decimal(90)]
    assert profits == [Decimal(-10)]
    assert assets == {asset.id_: [Decimal(0)]}


def test_get_value_fund_day(
    today_ord: int,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    values, profits, assets = account.get_value(today_ord - 3, today_ord - 3)
    assert values == [Decimal(100)]
    assert profits == [Decimal(0)]
    assert assets == {}


def test_get_cash_flow_empty(
    today_ord: int,
    session: orm.Session,
    account: Account,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = account.get_cash_flow(start_ord, end_ord)
    assert result == {}
    # defaultdict is correct length
    assert result[0] == [Decimal(0)] * 7

    result = Account.get_cash_flow_all(session, start_ord, end_ord)
    assert result == {}


def test_get_cash_flow(
    today_ord: int,
    account: Account,
    transactions: list[Transaction],
    categories: dict[str, int],
) -> None:
    _ = transactions
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = account.get_cash_flow(start_ord, end_ord)
    target = {
        categories["other income"]: [
            Decimal(100),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
            Decimal(0),
        ],
        categories["securities traded"]: [
            Decimal(0),
            Decimal(-10),
            Decimal(0),
            Decimal(0),
            Decimal(50),
            Decimal(0),
            Decimal(0),
        ],
    }
    assert result == target


def test_get_cash_flow_today(
    today_ord: int,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result = account.get_cash_flow(today_ord, today_ord)
    assert result == {}


def test_get_profit_by_asset_empty(
    today_ord: int,
    session: orm.Session,
    account: Account,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = account.get_profit_by_asset(start_ord, end_ord)
    assert result == {}
    assert result[0] == Decimal(0)

    result = Account.get_profit_by_asset_all(session, start_ord, end_ord)
    assert result == {}


def test_get_profit_by_asset(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
    asset_valuation: AssetValuation,
) -> None:
    _ = transactions
    _ = asset_valuation
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = account.get_profit_by_asset(start_ord, end_ord)
    target = {
        asset.id_: Decimal(90),
    }
    assert result == target


def test_get_profit_by_asset_today(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    result = account.get_profit_by_asset(today_ord, today_ord)
    assert result == {asset.id_: Decimal(0)}
