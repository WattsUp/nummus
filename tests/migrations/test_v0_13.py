from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_13 import MigratorV0_13
from nummus.models.label import Label, LabelLink
from nummus.models.transaction import TransactionSplit
from nummus.models.utils import (
    dump_table_configs,
    query_count,
)
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.12.0.db"
    path_db = tmp_path / "portfolio.v0.13.db"
    shutil.copyfile(path_original, path_db)

    p = Portfolio(path_db, None, check_migration=False)
    m = MigratorV0_13()
    result = m.migrate(p)
    target = []
    assert result == target

    with p.begin_session() as s:
        result = "\n".join(dump_table_configs(s, TransactionSplit))
        assert "label" not in result

        result = "\n".join(dump_table_configs(s, Label))
        assert "name" in result

        n = query_count(s.query(Label))
        assert n == 1

        result = "\n".join(dump_table_configs(s, LabelLink))
        assert "label_id" in result
        n = query_count(s.query(LabelLink))
        assert n == 100
