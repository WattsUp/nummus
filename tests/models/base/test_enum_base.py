from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.models import base

if TYPE_CHECKING:
    from collections.abc import Mapping


class Derived(base.BaseEnum):
    RED = 1
    BLUE = 2
    SEAFOAM_GREEN = 3

    @classmethod
    def _lut(cls) -> Mapping[str, Derived]:
        return {"r": cls.RED, "b": cls.BLUE}


def test_hasable() -> None:
    d = {
        Derived.RED: "red",
        Derived.BLUE: "blue",
    }
    assert isinstance(d, dict)


def test_missing() -> None:
    with pytest.raises(ValueError, match="None is not a valid Derived"):
        Derived(None)
    with pytest.raises(ValueError, match="'' is not a valid Derived"):
        Derived("")

    with pytest.raises(ValueError, match="'FAKE' is not a valid Derived"):
        Derived("FAKE")

    for e in Derived:
        assert Derived(e) == e
        assert Derived(e.name) == e
        assert Derived(e.value) == e

    for s, e in Derived._lut().items():  # noqa: SLF001
        assert Derived(s.upper()) == e


def test_comparators() -> None:
    assert Derived.RED == Derived.RED
    assert Derived.RED == "RED"

    assert Derived.RED != Derived.BLUE
    assert Derived.RED != "BLUE"


def test_str() -> None:
    assert str(Derived.RED) == "Derived.RED"
    assert str(Derived.SEAFOAM_GREEN) == "Derived.SEAFOAM_GREEN"


def test_pretty() -> None:
    assert Derived.RED.pretty == "Red"
    assert Derived.SEAFOAM_GREEN.pretty == "Seafoam Green"
