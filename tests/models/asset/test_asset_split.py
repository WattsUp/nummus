from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import exceptions as exc
from nummus.models import AssetSplit

if TYPE_CHECKING:
    import datetime

    from sqlalchemy import orm

    from nummus.models import Asset
    from tests.conftest import RandomRealGenerator


def test_init_properties(
    today: datetime.date,
    today_ord: int,
    session: orm.Session,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    d = {
        "asset_id": asset.id_,
        "multiplier": rand_real_generator(1, 10),
        "date_ord": today_ord,
    }

    v = AssetSplit(**d)
    session.add(v)
    session.commit()

    assert v.asset_id == d["asset_id"]
    assert v.multiplier == d["multiplier"]
    assert v.date_ord == d["date_ord"]
    assert v.date == today


def test_multiplier_negative(
    today_ord: int,
    session: orm.Session,
    asset: Asset,
) -> None:
    v = AssetSplit(asset_id=asset.id_, date_ord=today_ord, multiplier=-1)
    session.add(v)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_multiplier_zero(today_ord: int, session: orm.Session, asset: Asset) -> None:
    v = AssetSplit(asset_id=asset.id_, date_ord=today_ord, multiplier=0)
    session.add(v)
    with pytest.raises(exc.IntegrityError):
        session.commit()


def test_duplicate_dates(
    today_ord: int,
    session: orm.Session,
    asset: Asset,
    rand_real_generator: RandomRealGenerator,
) -> None:
    v = AssetSplit(
        asset_id=asset.id_,
        date_ord=today_ord,
        multiplier=rand_real_generator(1, 10),
    )
    session.add(v)
    v = AssetSplit(
        asset_id=asset.id_,
        date_ord=today_ord,
        multiplier=rand_real_generator(1, 10),
    )
    session.add(v)
    with pytest.raises(exc.IntegrityError):
        session.commit()
