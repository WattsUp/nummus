from __future__ import annotations

from typing import override, TYPE_CHECKING

import pytest
from packaging.version import Version

from nummus import exceptions as exc
from nummus.migrations.base import Migrator, SchemaMigrator
from nummus.models.asset import (
    Asset,
    AssetCategory,
    AssetValuation,
)
from nummus.models.utils import dump_table_configs
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.portfolio import Portfolio


class MockMigrator(Migrator):

    _VERSION = "999.0.0"

    @override
    def migrate(self, p: Portfolio) -> list[str]:
        return ["Comments"]


def test_version() -> None:
    m = MockMigrator()
    assert m.min_version() == Version("999.0.0")


def test_drop_column(session: orm.Session) -> None:
    m = MockMigrator()
    with session.begin_nested():
        m.drop_column(Asset, "category")
    assert m.pending_schema_updates == set()

    result = "\n".join(dump_table_configs(Asset))
    assert "category" not in result


def test_drop_column_with_constraints(session: orm.Session) -> None:
    m = MockMigrator()
    with session.begin_nested():
        m.drop_column(AssetValuation, "value")
    assert m.pending_schema_updates == {AssetValuation}

    result = "\n".join(dump_table_configs(AssetValuation))
    assert "value" not in result


def test_add_column_no_value_set(session: orm.Session, asset: Asset) -> None:
    m = MockMigrator()
    with session.begin_nested():
        m.drop_column(Asset, "category")
    m.pending_schema_updates.clear()

    with session.begin_nested():
        m.add_column(Asset, Asset.category)
    assert m.pending_schema_updates == {Asset}

    result = "\n".join(dump_table_configs(Asset))
    assert "category" in result

    asset.refresh()
    assert asset.category is None


def test_add_column_value_set(session: orm.Session, asset: Asset) -> None:
    m = MockMigrator()
    with session.begin_nested():
        m.drop_column(Asset, "category")
    m.pending_schema_updates.clear()

    with session.begin_nested():
        m.add_column(Asset, Asset.category, AssetCategory.STOCKS)
    assert m.pending_schema_updates == {Asset}

    result = "\n".join(dump_table_configs(Asset))
    assert "category" in result

    asset.refresh()
    assert asset.category == AssetCategory.STOCKS


def test_rename_column(session: orm.Session) -> None:
    m = MockMigrator()
    with session.begin_nested():
        m.rename_column(Asset, "category", "class")
    assert m.pending_schema_updates == {Asset}

    result = "\n".join(dump_table_configs(Asset))
    assert "category" not in result
    assert "class" in result


def test_migrate_schemas_no_value_set(empty_portfolio: Portfolio, asset: Asset) -> None:
    m = SchemaMigrator(set())
    with empty_portfolio.begin_session():
        m.drop_column(Asset, "category")
    with empty_portfolio.begin_session():
        m.add_column(Asset, Asset.category)

    with pytest.raises(exc.IntegrityError):
        m.migrate(empty_portfolio)


def test_migrate_schemas_value_set(empty_portfolio: Portfolio, asset: Asset) -> None:
    m = SchemaMigrator(set())
    with empty_portfolio.begin_session():
        m.drop_column(Asset, "category")
    with empty_portfolio.begin_session():
        m.add_column(Asset, Asset.category, AssetCategory.STOCKS)

    assert m.migrate(empty_portfolio) == []
