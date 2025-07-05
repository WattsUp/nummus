from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import global_config

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from tests.conftest import RandomString


def test_get(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rand_str: RandomString,
) -> None:
    path = tmp_path / "config.ini"
    monkeypatch.setattr(global_config, "_PATH", path)
    global_config._CACHE.clear()  # noqa: SLF001

    # Config file doesn't exist so expect defaults
    config = global_config.get()
    assert isinstance(config, dict)
    for k, v in global_config._DEFAULTS.items():  # noqa: SLF001
        assert config.pop(k) == v
    assert len(config) == 0

    with path.open("w", encoding="utf-8") as file:
        file.write("[nummus]\n")

    # Empty section should still be defaults
    config = global_config.get()
    assert isinstance(config, dict)
    for k, v in global_config._DEFAULTS.items():  # noqa: SLF001
        assert config.pop(k) == v
    assert len(config) == 0

    secure_icon = rand_str()
    with path.open("w", encoding="utf-8") as file:
        file.write(f"[nummus]\nsecure-icon = {secure_icon}\n")

    assert global_config.get(global_config.ConfigKey.SECURE_ICON) == secure_icon
    assert global_config.get("secure-icon") == secure_icon
