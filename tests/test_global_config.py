from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import global_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_get_non_existant(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "config.ini"
    monkeypatch.setattr(global_config, "_PATH", path)

    # Config file doesn't exist so expect defaults
    config = global_config.get()
    assert isinstance(config, dict)
    for k, v in global_config._DEFAULTS.items():
        assert config.pop(k) == v
    assert len(config) == 0


def test_get_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "config.ini"
    monkeypatch.setattr(global_config, "_PATH", path)
    with path.open("w", encoding="utf-8") as file:
        file.write("[nummus]\n")

    # Empty section should still be defaults
    config = global_config.get()
    assert isinstance(config, dict)
    for k, v in global_config._DEFAULTS.items():
        assert config.pop(k) == v
    assert len(config) == 0


def test_get_populated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rand_str: str,
) -> None:
    path = tmp_path / "config.ini"
    monkeypatch.setattr(global_config, "_PATH", path)
    with path.open("w", encoding="utf-8") as file:
        file.write(f"[nummus]\nsecure-icon = {rand_str}\n")

    assert global_config.get(global_config.ConfigKey.SECURE_ICON) == rand_str
    assert global_config.get("secure-icon") == rand_str
