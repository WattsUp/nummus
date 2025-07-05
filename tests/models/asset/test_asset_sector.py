from __future__ import annotations

from decimal import Decimal

from nummus import exceptions as exc
from nummus import models
from nummus.models import Asset, AssetCategory, AssetSector, USSector


def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    a = Asset(name=self.random_string(), category=AssetCategory.CASH)
    s.add(a)
    s.commit()

    d = {
        "asset_id": a.id_,
        "sector": USSector.REAL_ESTATE,
        "weight": self.random_decimal(0, 1),
    }

    v = AssetSector(**d)
    s.add(v)
    s.commit()

    assert v.asset_id == d["asset_id"]
    assert v.sector == d["sector"]
    assert v.weight == d["weight"]

    # Negative weights are bad
    v.weight = Decimal(-1)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Zero weightsare bad
    v.weight = Decimal(0)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Duplicate sectors are bad
    v = AssetSector(**d)
    s.add(v)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()
