from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models.asset import AssetSector, USSector

if TYPE_CHECKING:
    from nummus.models.asset import Asset
    from tests.conftest import RandomRealGenerator


def test_init_properties(
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    d = {
        "asset_id": asset.id_,
        "sector": USSector.REAL_ESTATE,
        "weight": rand_real_generator(1, 10),
    }

    v = AssetSector.create(**d)

    assert v.asset_id == d["asset_id"]
    assert v.sector == d["sector"]
    assert v.weight == d["weight"]


def test_weight_negative(asset: Asset) -> None:
    with pytest.raises(exc.IntegrityError):
        AssetSector.create(asset_id=asset.id_, sector=USSector.REAL_ESTATE, weight=-1)


def test_weight_zero(asset: Asset) -> None:
    with pytest.raises(exc.IntegrityError):
        AssetSector.create(asset_id=asset.id_, sector=USSector.REAL_ESTATE, weight=0)


def test_duplicate_sectors(
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    AssetSector.create(
        asset_id=asset.id_,
        sector=USSector.REAL_ESTATE,
        weight=rand_real_generator(1, 10),
    )
    with pytest.raises(exc.IntegrityError):
        AssetSector.create(
            asset_id=asset.id_,
            sector=USSector.REAL_ESTATE,
            weight=rand_real_generator(1, 10),
        )
