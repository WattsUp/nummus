from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_15 import MigratorV0_15
from nummus.models import (
    dump_table_configs,
    Label,
    LabelLink,
    query_count,
)
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


def test_migrate(tmp_path: Path, data_path: Path) -> None:
    path_original = data_path / "old_versions" / "v0.14.0.db"
    path_db = tmp_path / "portfolio.v0.15.db"
    shutil.copyfile(path_original, path_db)

    p = Portfolio(path_db, None, check_migration=False)
    m = MigratorV0_15()
    result = m.migrate(p)
    target = []
    assert result == target

    with p.begin_session() as s:
        result = "\n".join(dump_table_configs(s, Label))
        assert "name" in result

        n = query_count(s.query(Label))
        assert n == 1

        result = "\n".join(dump_table_configs(s, LabelLink))
        assert "label_id" in result
        n = query_count(s.query(LabelLink))
        assert n == 100
