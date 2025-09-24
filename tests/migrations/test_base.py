from __future__ import annotations

from typing import override, TYPE_CHECKING

import pytest
from packaging.version import Version

from nummus import exceptions as exc
from nummus import migrations
from nummus.migrations.base import SchemaMigrator
from nummus.models import Asset, AssetCategory, AssetValuation, dump_table_configs

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.portfolio import Portfolio


class MockMigrator(migrations.Migrator):

    _VERSION = "999.0.0"

    @override
    def migrate(self, p: Portfolio) -> list[str]:
        _ = p
        return ["Comments"]


def test_version() -> None:
    m = MockMigrator()
    assert m.min_version() == Version("999.0.0")


def test_drop_column(session: orm.Session) -> None:
    m = MockMigrator()
    m.drop_column(session, Asset, "category")
    session.commit()
    assert m.pending_schema_updates == set()

    result = "\n".join(dump_table_configs(session, Asset))
    assert "category" not in result


def test_drop_column_with_constraints(session: orm.Session) -> None:
    m = MockMigrator()
    m.drop_column(session, AssetValuation, "value")
    session.commit()
    assert m.pending_schema_updates == {AssetValuation}

    result = "\n".join(dump_table_configs(session, AssetValuation))
    assert "value" not in result


def test_add_column_no_value_set(session: orm.Session, asset: Asset) -> None:
    m = MockMigrator()
    m.drop_column(session, Asset, "category")
    session.commit()
    m.pending_schema_updates.clear()

    m.add_column(session, Asset, Asset.category)
    session.commit()
    assert m.pending_schema_updates == {Asset}

    result = "\n".join(dump_table_configs(session, Asset))
    assert "category" in result

    assert asset.category is None


def test_add_column_value_set(session: orm.Session, asset: Asset) -> None:
    m = MockMigrator()
    m.drop_column(session, Asset, "category")
    session.commit()
    m.pending_schema_updates.clear()

    m.add_column(session, Asset, Asset.category, AssetCategory.STOCKS)
    session.commit()
    assert m.pending_schema_updates == {Asset}

    result = "\n".join(dump_table_configs(session, Asset))
    assert "category" in result

    assert asset.category == AssetCategory.STOCKS


def test_rename_column(session: orm.Session) -> None:
    m = MockMigrator()
    m.rename_column(session, Asset, "category", "class")
    session.commit()
    assert m.pending_schema_updates == {Asset}

    result = "\n".join(dump_table_configs(session, Asset))
    assert "category" not in result
    assert "class" in result


def test_migrate_schemas_no_value_set(empty_portfolio: Portfolio, asset: Asset) -> None:
    _ = asset
    m = SchemaMigrator(set())
    with empty_portfolio.begin_session() as s:
        m.drop_column(s, Asset, "category")
    with empty_portfolio.begin_session() as s:
        m.add_column(s, Asset, Asset.category)

    with pytest.raises(exc.IntegrityError):
        m.migrate(empty_portfolio)


def test_migrate_schemas_value_set(empty_portfolio: Portfolio, asset: Asset) -> None:
    _ = asset
    m = SchemaMigrator(set())
    with empty_portfolio.begin_session() as s:
        m.drop_column(s, Asset, "category")
    with empty_portfolio.begin_session() as s:
        m.add_column(s, Asset, Asset.category, AssetCategory.STOCKS)

    assert m.migrate(empty_portfolio) == []
