from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus import sql
from nummus.migrations.v0_15 import MigratorV0_15
from nummus.models.label import Label, LabelLink
from nummus.models.utils import dump_table_configs
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

    with p.begin_session():
        result = "\n".join(dump_table_configs(Label))
        assert "name" in result

        assert sql.count(Label.query()) == 1

        result = "\n".join(dump_table_configs(LabelLink))
        assert "label_id" in result
        assert sql.count(LabelLink.query()) == 100
