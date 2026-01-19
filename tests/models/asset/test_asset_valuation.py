from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.asset import AssetValuation

if TYPE_CHECKING:
    import datetime
    from decimal import Decimal

    from nummus.models.asset import Asset
    from tests.conftest import RandomRealGenerator


def test_init_properties(
    today: datetime.date,
    today_ord: int,
    asset: Asset,
    rand_real: Decimal,
) -> None:
    d = {
        "asset_id": asset.id_,
        "date_ord": today_ord,
        "value": rand_real,
    }

    v = AssetValuation.create(**d)

    assert v.asset_id == d["asset_id"]
    assert v.value == d["value"]
    assert v.date_ord == d["date_ord"]
    assert v.date == today


def test_multiplier_negative(
    today_ord: int,
    asset: Asset,
) -> None:
    with pytest.raises(exc.IntegrityError):
        AssetValuation.create(asset_id=asset.id_, date_ord=today_ord, value=-1)


def test_duplicate_dates(
    today_ord: int,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    AssetValuation.create(
        asset_id=asset.id_,
        date_ord=today_ord,
        value=rand_real_generator(),
    )
    with pytest.raises(exc.IntegrityError):
        AssetValuation.create(
            asset_id=asset.id_,
            date_ord=today_ord,
            value=rand_real_generator(),
        )
