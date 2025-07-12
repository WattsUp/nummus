from __future__ import annotations

from nummus.models import USSector


def test_init_properties() -> None:
    s = USSector("realestate")
    assert s == USSector.REAL_ESTATE
