from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus import sql
from nummus.models.asset import (
    Asset,
    AssetCategory,
    AssetSector,
    AssetValuation,
    USSector,
)
from nummus.models.currency import Currency, DEFAULT_CURRENCY
from nummus.models.label import LabelLink
from nummus.models.utils import update_rows
from tests import conftest

if TYPE_CHECKING:
    from nummus.models.account import Account
    from nummus.models.asset import AssetSplit
    from nummus.models.transaction import Transaction
    from tests.conftest import RandomStringGenerator


@pytest.fixture
def valuations(
    today_ord: int,
    asset: Asset,
) -> list[AssetValuation]:
    a_id = asset.id_
    updates: dict[object, dict[str, object]] = {
        today_ord - 3: {"value": Decimal(10), "asset_id": a_id},
        today_ord: {"value": Decimal(100), "asset_id": a_id},
        today_ord + 3: {"value": Decimal(10), "asset_id": a_id},
    }

    update_rows(AssetValuation, AssetValuation.query(), "date_ord", updates)
    return AssetValuation.all()


@pytest.fixture
def valuations_five(
    today_ord: int,
    asset: Asset,
) -> list[AssetValuation]:
    a_id = asset.id_
    updates: dict[object, dict[str, object]] = {
        today_ord - 7: {"value": Decimal(10), "asset_id": a_id},
        today_ord - 3: {"value": Decimal(10), "asset_id": a_id},
        today_ord: {"value": Decimal(100), "asset_id": a_id},
        today_ord + 3: {"value": Decimal(10), "asset_id": a_id},
        today_ord + 7: {"value": Decimal(10), "asset_id": a_id},
    }

    update_rows(AssetValuation, AssetValuation.query(), "date_ord", updates)
    return AssetValuation.all()


def test_init_properties(
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "name": rand_str_generator(),
        "description": rand_str_generator(),
        "category": AssetCategory.STOCKS,
        "ticker": "A",
        "currency": DEFAULT_CURRENCY,
    }

    a = Asset.create(**d)

    assert a.name == d["name"]
    assert a.description == d["description"]
    assert a.category == d["category"]
    assert a.ticker == d["ticker"]


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        Asset(name="a")


def test_get_value_empty(
    today_ord: int,
    asset: Asset,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = asset.get_value(start_ord, end_ord)
    assert result == [Decimal(0)] * 7

    result = Asset.get_value_all(start_ord, end_ord)
    assert result == {}


def test_get_value(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = asset.get_value(start_ord, end_ord)
    target = [
        Decimal(10),
        Decimal(10),
        Decimal(10),
        Decimal(100),
        Decimal(100),
        Decimal(100),
        Decimal(10),
    ]
    assert result == target


def test_get_value_interpolate(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    asset.interpolate = True
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = asset.get_value(start_ord, end_ord)
    target = [
        Decimal(10),
        Decimal(40),
        Decimal(70),
        Decimal(100),
        Decimal(70),
        Decimal(40),
        Decimal(10),
    ]
    assert result == target


def test_get_value_today(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    result = asset.get_value(today_ord, today_ord)
    assert result == [Decimal(100)]


def test_get_value_tomorrow_interpolate(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    asset.interpolate = True
    result = asset.get_value(today_ord + 1, today_ord + 1)
    assert result == [Decimal(70)]


def test_update_splits_empty(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    asset.update_splits()
    assets = account.get_asset_qty(today_ord, today_ord)
    assert assets == {asset.id_: [Decimal(10)]}


def test_update_splits(
    today_ord: int,
    account: Account,
    asset: Asset,
    asset_split: AssetSplit,
    transactions: list[Transaction],
) -> None:
    asset.update_splits()
    assets = account.get_asset_qty(today_ord, today_ord)
    assert assets == {asset.id_: [Decimal(100)]}
    assets = account.get_asset_qty(today_ord + 7, today_ord + 7)
    assert assets == {asset.id_: [Decimal(0)]}


def test_prune_valuations_all(asset: Asset, valuations: list[AssetValuation]) -> None:
    assert asset.prune_valuations() == len(valuations)


def test_prune_valuations_none(
    asset: Asset,
    valuations: list[AssetValuation],
    transactions: list[Transaction],
) -> None:
    assert asset.prune_valuations() == 0


@pytest.mark.parametrize(
    ("to_delete", "target"),
    [
        ([], 1),
        ([0], 1),
        ([0, 1], 2),
        ([0, 1, 2], 4),
        ([0, 1, 2, 3], 5),
        ([1, 2, 3], 5),
        ([2, 3], 1),
        ([3], 1),
    ],
    ids=conftest.id_func,
)
def test_prune_valuations_first_txn(
    asset: Asset,
    valuations_five: list[AssetValuation],
    transactions: list[Transaction],
    to_delete: list[int],
    target: int,
) -> None:
    for i in to_delete:
        txn = transactions[i]
        for t_split in txn.splits:
            LabelLink.query().where(LabelLink.t_split_id == t_split.id_).delete()
            t_split.delete()
        txn.delete()
    assert asset.prune_valuations() == target


def test_prune_valuations_index(asset: Asset, valuations: list[AssetValuation]) -> None:
    asset.category = AssetCategory.INDEX
    assert asset.prune_valuations() == 0


def test_update_valuations_none(asset: Asset) -> None:
    asset.ticker = None
    with pytest.raises(exc.NoAssetWebSourceError):
        asset.update_valuations(through_today=True)


def test_update_valuations_empty(asset: Asset) -> None:
    start, end = asset.update_valuations(through_today=True)
    assert start is None
    assert end is None
    assert not sql.any_(AssetValuation.query())


@pytest.mark.parametrize(
    ("category", "ticker", "i_txn"),
    [
        (AssetCategory.STOCKS, "BANANA", 1),
        (AssetCategory.INDEX, "^BANANA", 1),
        (AssetCategory.FOREX, "BANANA=X", 0),
    ],
)
def test_update_valuations(
    today: datetime.date,
    transactions: list[Transaction],
    category: AssetCategory,
    asset: Asset,
    ticker: str,
    i_txn: int,
) -> None:
    asset.category = category
    asset.ticker = ticker

    start, end = asset.update_valuations(through_today=True)
    # 7 days before first transaction
    assert start is not None
    assert end is not None
    assert start == (transactions[i_txn].date - datetime.timedelta(days=7))
    assert end == today

    n = 0
    while start <= end:
        n += 0 if start.weekday() in {5, 6} else 1
        start += datetime.timedelta(days=1)
    assert sql.count(AssetValuation.query()) == n


def test_update_valuations_delisted(
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    asset.ticker = "APPLE"
    with pytest.raises(exc.AssetWebError):
        asset.update_valuations(through_today=True)


def test_update_sectors_none(asset: Asset) -> None:
    asset.ticker = None
    with pytest.raises(exc.NoAssetWebSourceError):
        asset.update_sectors()


@pytest.mark.parametrize(
    ("ticker", "target"),
    [
        ("BANANA", {USSector.HEALTHCARE: Decimal(1)}),
        (
            "BANANA_ETF",
            {
                USSector.REAL_ESTATE: Decimal("0.1"),
                USSector.ENERGY: Decimal("0.9"),
            },
        ),
        ("ORANGE", {}),
        (
            "ORANGE_ETF",
            {
                USSector.REAL_ESTATE: Decimal("0.1"),
                USSector.TECHNOLOGY: Decimal("0.5"),
                USSector.FINANCIAL_SERVICES: Decimal("0.4"),
            },
        ),
    ],
)
def test_update_sectors(
    asset: Asset,
    ticker: str,
    target: dict[USSector, Decimal],
) -> None:
    asset.ticker = ticker
    asset.update_sectors()
    query = AssetSector.query(AssetSector.sector, AssetSector.weight).where(
        AssetSector.asset_id == asset.id_,
    )
    sectors: dict[USSector, Decimal] = sql.to_dict(query)
    assert sectors == target


def test_index_twrr_none(today_ord: int) -> None:
    with pytest.raises(exc.ProtectedObjectNotFoundError):
        Asset.index_twrr("Fake Index", today_ord, today_ord)


def test_index_twrr(today_ord: int, asset: Asset) -> None:
    asset.category = AssetCategory.INDEX
    result = Asset.index_twrr(asset.name, today_ord - 3, today_ord + 3)
    # utils.twrr and Asset.get_value already tested, just check they connect well
    assert result == [Decimal(0)] * 7


def test_index_twrr_today(today_ord: int, asset: Asset) -> None:
    asset.category = AssetCategory.INDEX
    result = Asset.index_twrr(asset.name, today_ord, today_ord)
    assert result == [Decimal(0)]


def test_add_indices() -> None:
    for asset in Asset.all():
        assert asset.name is not None
        assert asset.description is not None
        assert not asset.interpolate
        assert asset.category == AssetCategory.INDEX


def test_autodetect_interpolate_empty(asset: Asset) -> None:
    asset.autodetect_interpolate()
    assert not asset.interpolate


def test_autodetect_interpolate_sparse(
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    asset.autodetect_interpolate()
    assert asset.interpolate


def test_autodetect_interpolate_daily(
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    for i, v in enumerate(valuations):
        v.date_ord = valuations[0].date_ord + i
    asset.autodetect_interpolate()
    assert not asset.interpolate


def test_create_forex(asset: Asset) -> None:
    asset.ticker = "EURUSD=X"
    asset.category = AssetCategory.FOREX

    Asset.create_forex(Currency.USD, {*Currency})

    query = Asset.query().where(Asset.category == AssetCategory.FOREX)
    # -1 since don't need USDUSD=x
    assert sql.count(query) == len(Currency) - 1


def test_create_forex_none() -> None:
    Asset.create_forex(Currency.USD, set())

    query = Asset.query().where(Asset.category == AssetCategory.FOREX)
    assert not sql.any_(query)


def test_get_forex_empty(today_ord: int) -> None:
    result = Asset.get_forex(today_ord, today_ord, DEFAULT_CURRENCY)
    assert result[DEFAULT_CURRENCY] == [Decimal(1)]


def test_get_forex(
    today_ord: int,
    asset: Asset,
    asset_valuation: AssetValuation,
) -> None:
    asset.ticker = "EURUSD=X"
    asset.category = AssetCategory.FOREX
    asset.currency = Currency.USD

    result = Asset.get_forex(
        today_ord,
        today_ord,
        Currency.USD,
        {Currency.EUR},
    )
    assert result[Currency.EUR] == [asset_valuation.value]
