from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from nummus.migrations.v0_13 import MigratorV0_13
from nummus.models import (
    dump_table_configs,
    query_count,
    Tag,
    TagLink,
    TransactionSplit,
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
        assert "tag" not in result

        result = "\n".join(dump_table_configs(s, Tag))
        assert "name" in result

        n = query_count(s.query(Tag))
        assert n == 1

        result = "\n".join(dump_table_configs(s, TagLink))
        assert "tag_id" in result
        n = query_count(s.query(TagLink))
        assert n == 100
