from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.asset import AssetSplit

if TYPE_CHECKING:
    import datetime

    from nummus.models.asset import Asset
    from tests.conftest import RandomRealGenerator


def test_init_properties(
    today: datetime.date,
    today_ord: int,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    d = {
        "asset_id": asset.id_,
        "multiplier": rand_real_generator(1, 10),
        "date_ord": today_ord,
    }

    v = AssetSplit.create(**d)

    assert v.asset_id == d["asset_id"]
    assert v.multiplier == d["multiplier"]
    assert v.date_ord == d["date_ord"]
    assert v.date == today


def test_multiplier_negative(
    today_ord: int,
    asset: Asset,
) -> None:
    with pytest.raises(exc.IntegrityError):
        AssetSplit.create(asset_id=asset.id_, date_ord=today_ord, multiplier=-1)


def test_multiplier_zero(today_ord: int, asset: Asset) -> None:
    with pytest.raises(exc.IntegrityError):
        AssetSplit.create(asset_id=asset.id_, date_ord=today_ord, multiplier=0)


def test_duplicate_dates(
    today_ord: int,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    AssetSplit.create(
        asset_id=asset.id_,
        date_ord=today_ord,
        multiplier=rand_real_generator(1, 10),
    )
    with pytest.raises(exc.IntegrityError):
        AssetSplit.create(
            asset_id=asset.id_,
            date_ord=today_ord,
            multiplier=rand_real_generator(1, 10),
        )
