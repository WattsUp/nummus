from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import AssetSector, USSector

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import Asset
    from tests.conftest import RandomRealGenerator


def test_init_properties(
    session: orm.Session,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    d = {
        "asset_id": asset.id_,
        "sector": USSector.REAL_ESTATE,
        "weight": rand_real_generator(1, 10),
    }

    v = AssetSector(**d)
    session.add(v)
    session.commit()

    assert v.asset_id == d["asset_id"]
    assert v.sector == d["sector"]
    assert v.weight == d["weight"]


def test_weight_negative(session: orm.Session, asset: Asset) -> None:
    v = AssetSector(asset_id=asset.id_, sector=USSector.REAL_ESTATE, weight=-1)
    session.add(v)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_weight_zero(session: orm.Session, asset: Asset) -> None:
    v = AssetSector(asset_id=asset.id_, sector=USSector.REAL_ESTATE, weight=0)
    session.add(v)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_duplicate_sectors(
    session: orm.Session,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    v = AssetSector(
        asset_id=asset.id_,
        sector=USSector.REAL_ESTATE,
        weight=rand_real_generator(1, 10),
    )
    session.add(v)
    v = AssetSector(
        asset_id=asset.id_,
        sector=USSector.REAL_ESTATE,
        weight=rand_real_generator(1, 10),
    )
    session.add(v)
    with pytest.raises(exc.IntegrityError):
        session.commit()
