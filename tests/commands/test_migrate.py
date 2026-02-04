from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.commands.migrate import Migrate

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from nummus.portfolio import Portfolio


def test_not_required(
    capsys: pytest.CaptureFixture[str],
    empty_portfolio: Portfolio,
) -> None:

    c = Migrate(empty_portfolio.path, None)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = "Portfolio is unlocked\nPortfolio does not need migration\n"
    assert captured.out == target
    assert not captured.err


def test_v0_1_migration(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    data_path: Path,
) -> None:
    path = tmp_path / "portfolio.db"
    shutil.copyfile(data_path / "old_versions" / "v0.1.16.db", path)

    c = Migrate(path, None)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = (
        "Portfolio is unlocked\n"
        "This transaction had multiple payees, only one allowed: "
        "1948-03-15 Savings, please validate\n"
        "Portfolio migrated to v0.2.0\n"
        "Portfolio migrated to v0.10.0\n"
        "Portfolio migrated to v0.11.0\n"
        "Portfolio migrated to v0.13.0\n"
        "Portfolio migrated to v0.15.0\n"
        "Portfolio currency set to USD (US Dollar), use web to edit\n"
        "Portfolio migrated to v0.16.0\n"
        "Portfolio model schemas updated\n"
    )
    assert captured.out == target
    assert not captured.err
