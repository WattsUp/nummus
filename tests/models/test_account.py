from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import Account, AccountCategory

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Asset, AssetValuation, Transaction
    from tests.conftest import RandomStringGenerator


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
    assert account.updated_on_ord == today_ord + 7


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
    assert result[0] == [Decimal()] * 7

    result = Account.get_asset_qty_all(session, start_ord, end_ord)
    assert result == {}


def test_get_asset_qty_none(
    today_ord: int,
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = account
    _ = transactions
    start_ord = today_ord - 3
    end_ord = today_ord + 3

    result = Account.get_asset_qty_all(session, start_ord, end_ord, set())
    # defaultdict is correct length
    assert result[0][0] == [Decimal()] * 7


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
            Decimal(),
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
    assert values == [Decimal()] * 7
    assert profits == [Decimal()] * 7
    assert assets == {}
    # defaultdict is correct length
    assert assets[0] == [Decimal()] * 7

    values, profits, assets = Account.get_value_all(session, start_ord, end_ord)
    assert values == {}
    assert profits == {}
    assert assets == {}


def test_get_value_none(
    today_ord: int,
    session: orm.Session,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = account
    _ = transactions
    start_ord = today_ord - 3
    end_ord = today_ord + 3

    values, profits, assets = Account.get_value_all(session, start_ord, end_ord, set())
    assert values == {}
    assert profits == {}
    assert assets == {}

    # defaultdict is correct length
    assert assets[0] == [Decimal()] * 7


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
        Decimal(),
        Decimal(100),
        Decimal(90),
        Decimal(90),
        Decimal(110),
        Decimal(150),
        Decimal(150),
        Decimal(150),
    ]
    assert values == target
    target = [
        Decimal(),
        Decimal(),
        Decimal(-10),
        Decimal(-10),
        Decimal(10),
        Decimal(50),
        Decimal(50),
        Decimal(50),
    ]
    assert profits == target
    target = {
        asset.id_: [
            Decimal(),
            Decimal(),
            Decimal(),
            Decimal(),
            Decimal(20),
            Decimal(10),
            Decimal(10),
            Decimal(10),
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
    assert values == [Decimal(110)]
    assert profits == [Decimal()]
    assert assets == {asset.id_: [Decimal(20)]}


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
    assert assets == {asset.id_: [Decimal()]}


def test_get_value_fund_day(
    today_ord: int,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    values, profits, assets = account.get_value(today_ord - 3, today_ord - 3)
    assert values == [Decimal(100)]
    assert profits == [Decimal()]
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
    assert result[0] == [Decimal()] * 7

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
            Decimal(),
            Decimal(),
            Decimal(),
            Decimal(),
            Decimal(),
            Decimal(),
        ],
        categories["securities traded"]: [
            Decimal(),
            Decimal(-10),
            Decimal(),
            Decimal(),
            Decimal(50),
            Decimal(),
            Decimal(),
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
    assert result[0] == Decimal()

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
        asset.id_: Decimal(50),
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
    assert result == {asset.id_: Decimal()}


def test_do_include(
    today_ord: int,
    account: Account,
) -> None:
    assert account.do_include(today_ord)


def test_dont_include_closed(
    today_ord: int,
    account: Account,
) -> None:
    account.closed = True
    assert not account.do_include(today_ord)


def test_do_include_closed(
    today_ord: int,
    account: Account,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    account.closed = True
    assert account.do_include(today_ord)
