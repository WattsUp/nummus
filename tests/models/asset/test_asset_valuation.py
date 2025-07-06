from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from nummus import exceptions as exc
from nummus import models
from nummus.models import Asset, AssetCategory, AssetValuation


@pytest.mark.xfail
def test_init_properties() -> None:
    s = self.get_session()
    models.metadata_create_all(s)

    today = datetime.datetime.now().astimezone().date()
    today_ord = today.toordinal()

    a = Asset(name=self.random_string(), category=AssetCategory.CASH)
    s.add(a)
    s.commit()

    d = {
        "asset_id": a.id_,
        "value": self.random_decimal(0, 1),
        "date_ord": today_ord,
    }

    v = AssetValuation(**d)
    s.add(v)
    s.commit()

    assert v.asset_id == d["asset_id"]
    assert v.value == d["value"]
    assert v.date_ord == d["date_ord"]

    # Negative amounts are bad
    v.value = Decimal(-1)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()

    # Duplicate dates are bad
    v = AssetValuation(**d)
    s.add(v)
    self.assertRaises(exc.IntegrityError, s.commit)
    s.rollback()
