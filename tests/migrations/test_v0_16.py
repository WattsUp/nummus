from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_16 import MigratorV0_16
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.config import Config
from nummus.models.currency import Currency
from nummus.models.utils import dump_table_configs
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.15.5.db"
    path_db = tmp_path / "portfolio.v0.16.db"
    shutil.copyfile(path_original, path_db)

    p = Portfolio(path_db, None, check_migration=False)
    m = MigratorV0_16()
    result = m.migrate(p)
    target = [
        "Portfolio currency set to USD (US Dollar), use web to edit",
    ]
    assert result == target

    with p.begin_session() as s:
        result = "\n".join(dump_table_configs(s, Account))
        assert "currency" in result

        result = "\n".join(dump_table_configs(s, Asset))
        assert "currency" in result

        assert Config.base_currency(s) == Currency.USD
