from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_11 import MigratorV0_11
from nummus.models import (
    AssetSector,
    AssetSplit,
    AssetValuation,
    BudgetAssignment,
    Target,
    Transaction,
    TransactionSplit,
)
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.10.1.db"
    path_db = tmp_path / "portfolio.v0.11.db"
    shutil.copyfile(path_original, path_db)

    p = Portfolio(path_db, None, check_migration=False)
    m = MigratorV0_11()
    result = m.migrate(p)
    target = []
    assert result == target

    assert m.pending_schema_updates == {
        AssetSector,
        AssetSplit,
        AssetValuation,
        BudgetAssignment,
        Target,
        Transaction,
        TransactionSplit,
    }
