from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import (
    Asset,
    AssetCategory,
    AssetSector,
    AssetValuation,
    LabelLink,
    query_count,
    query_to_dict,
    update_rows,
    USSector,
)
from tests import conftest

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Account,
        AssetSplit,
        Transaction,
    )
    from tests.conftest import RandomStringGenerator


@pytest.fixture
def valuations(
    session: orm.Session,
    today_ord: int,
    asset: Asset,
) -> list[AssetValuation]:
    a_id = asset.id_
    updates: dict[object, dict[str, object]] = {
        today_ord - 3: {"value": Decimal(10), "asset_id": a_id},
        today_ord: {"value": Decimal(100), "asset_id": a_id},
        today_ord + 3: {"value": Decimal(10), "asset_id": a_id},
    }

    query = session.query(AssetValuation)
    update_rows(session, AssetValuation, query, "date_ord", updates)
    session.commit()
    return query.all()


@pytest.fixture
def valuations_five(
    session: orm.Session,
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

    query = session.query(AssetValuation)
    update_rows(session, AssetValuation, query, "date_ord", updates)
    session.commit()
    return query.all()


def test_init_properties(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    d = {
        "name": rand_str_generator(),
        "description": rand_str_generator(),
        "category": AssetCategory.STOCKS,
        "ticker": "A",
    }

    a = Asset(**d)
    session.add(a)
    session.commit()

    assert a.name == d["name"]
    assert a.description == d["description"]
    assert a.category == d["category"]
    assert a.ticker == d["ticker"]


def test_short() -> None:
    with pytest.raises(exc.InvalidORMValueError):
        Asset(name="a")


def test_get_value_empty(
    today_ord: int,
    session: orm.Session,
    asset: Asset,
) -> None:
    start_ord = today_ord - 3
    end_ord = today_ord + 3
    result = asset.get_value(start_ord, end_ord)
    assert result == [Decimal(0)] * 7

    result = Asset.get_value_all(session, start_ord, end_ord)
    assert result == {}


def test_get_value(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    _ = valuations
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
    _ = valuations
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
    _ = valuations
    result = asset.get_value(today_ord, today_ord)
    assert result == [Decimal(100)]


def test_get_value_tomorrow_interpolate(
    today_ord: int,
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    asset.interpolate = True
    _ = valuations
    result = asset.get_value(today_ord + 1, today_ord + 1)
    assert result == [Decimal(70)]


def test_update_splits_empty(
    today_ord: int,
    account: Account,
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
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
    _ = transactions
    _ = asset_split
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
    _ = valuations
    _ = transactions
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
    session: orm.Session,
    asset: Asset,
    valuations_five: list[AssetValuation],
    transactions: list[Transaction],
    to_delete: list[int],
    target: int,
) -> None:
    for i in to_delete:
        txn = transactions[i]
        for t_split in txn.splits:
            session.query(LabelLink).where(LabelLink.t_split_id == t_split.id_).delete()
            session.delete(t_split)
        session.delete(txn)
    _ = valuations_five
    assert asset.prune_valuations() == target


def test_prune_valuations_index(asset: Asset, valuations: list[AssetValuation]) -> None:
    _ = valuations
    asset.category = AssetCategory.INDEX
    assert asset.prune_valuations() == 0


def test_update_valuations_none(session: orm.Session, asset: Asset) -> None:
    asset.ticker = None
    session.commit()
    with pytest.raises(exc.NoAssetWebSourceError):
        asset.update_valuations(through_today=True)


def test_update_valuations_empty(session: orm.Session, asset: Asset) -> None:
    start, end = asset.update_valuations(through_today=True)
    assert start is None
    assert end is None
    assert query_count(session.query(AssetValuation)) == 0


@pytest.mark.parametrize(
    ("category", "ticker"),
    [
        (AssetCategory.STOCKS, "BANANA"),
        (AssetCategory.INDEX, "^BANANA"),
    ],
)
def test_update_valuations(
    today: datetime.date,
    session: orm.Session,
    transactions: list[Transaction],
    category: AssetCategory,
    ticker: str,
) -> None:
    _ = transactions

    # Get first Asset
    asset = session.query(Asset).where(Asset.category == category).first()
    assert asset is not None
    asset.ticker = ticker

    start, end = asset.update_valuations(through_today=True)
    # 7 days before first transaction
    assert start == (today - datetime.timedelta(days=2 + 7))
    assert end == today
    n_weekdays = {
        0: 6,
        1: 7,
        2: 8,
        3: 8,
        4: 8,
        5: 7,
        6: 6,
    }[today.weekday()]
    assert query_count(session.query(AssetValuation)) == n_weekdays


def test_update_valuations_delisted(
    asset: Asset,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    asset.ticker = "APPLE"
    with pytest.raises(exc.AssetWebError):
        asset.update_valuations(through_today=True)


def test_update_sectors_none(session: orm.Session, asset: Asset) -> None:
    asset.ticker = None
    session.commit()
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
    session: orm.Session,
    asset: Asset,
    ticker: str,
    target: dict[USSector, Decimal],
) -> None:
    asset.ticker = ticker
    asset.update_sectors()
    session.commit()
    query = (
        session.query(AssetSector)
        .with_entities(AssetSector.sector, AssetSector.weight)
        .where(AssetSector.asset_id == asset.id_)
    )
    sectors: dict[USSector, Decimal] = query_to_dict(query)
    assert sectors == target


def test_index_twrr_none(today_ord: int, session: orm.Session) -> None:
    with pytest.raises(exc.ProtectedObjectNotFoundError):
        Asset.index_twrr(session, "Fake Index", today_ord, today_ord)


def test_index_twrr(today_ord: int, session: orm.Session, asset: Asset) -> None:
    asset.category = AssetCategory.INDEX
    result = Asset.index_twrr(session, asset.name, today_ord - 3, today_ord + 3)
    # utils.twrr and Asset.get_value already tested, just check they connect well
    assert result == [Decimal(0)] * 7


def test_index_twrr_today(today_ord: int, session: orm.Session, asset: Asset) -> None:
    asset.category = AssetCategory.INDEX
    result = Asset.index_twrr(session, asset.name, today_ord, today_ord)
    assert result == [Decimal(0)]


def test_add_indices(session: orm.Session) -> None:
    for asset in session.query(Asset).all():
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
    _ = valuations
    asset.autodetect_interpolate()
    assert asset.interpolate


def test_autodetect_interpolate_daily(
    asset: Asset,
    valuations: list[AssetValuation],
) -> None:
    for i, v in enumerate(valuations):
        v.date_ord = valuations[0].date_ord + i
    _ = valuations
    asset.autodetect_interpolate()
    assert not asset.interpolate
