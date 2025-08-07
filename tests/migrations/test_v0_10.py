from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_10 import MigratorV0_10
from nummus.models import dump_table_configs, TransactionCategory
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.9.5.db"
    path_db = tmp_path / "portfolio.v0.10.db"
    shutil.copyfile(path_original, path_db)

    p = Portfolio(path_db, None, check_migration=False)
    m = MigratorV0_10()
    result = m.migrate(p)
    target = []
    assert result == target

    with p.begin_session() as s:
        result = "\n".join(dump_table_configs(s, TransactionCategory))
        assert "essential_spending" in result
        assert TransactionCategory in m.pending_schema_updates
