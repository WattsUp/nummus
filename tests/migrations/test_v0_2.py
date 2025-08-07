from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_2 import MigratorV0_2
from nummus.models import dump_table_configs, Transaction, TransactionSplit
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.1.16.db"
    path_db = tmp_path / "portfolio.v0.2.db"
    shutil.copyfile(path_original, path_db)

    p = Portfolio(path_db, None, check_migration=False)
    m = MigratorV0_2()
    result = m.migrate(p)
    target = [
        "This transaction had multiple payees, only one allowed: "
        "1948-03-15 Savings, please validate",
    ]
    assert result == target

    with p.begin_session() as s:
        result = "\n".join(dump_table_configs(s, Transaction))
        assert "linked" not in result
        assert "locked" not in result
        assert "cleared" in result
        assert "payee" in result

        result = "\n".join(dump_table_configs(s, TransactionSplit))
        assert "linked" not in result
        assert "locked" not in result
        assert "cleared" in result
        assert "memo" in result
        # description is in name of check constraint until schema updates
        # Make sure it will be updated
        assert TransactionSplit in m.pending_schema_updates
