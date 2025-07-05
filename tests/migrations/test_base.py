from __future__ import annotations

import datetime
import secrets
from decimal import Decimal

from packaging.version import Version
from typing_extensions import override

from nummus import exceptions as exc
from nummus import migrations, portfolio
from nummus.models import Asset, AssetCategory, AssetValuation, dump_table_configs
from tests.base import TestBase


class MockMigrator(migrations.Migrator):

    _VERSION = "999.0.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        _ = p
        return ["Comments"]


class TestMigrator(TestBase):
    def test_init_properties(self) -> None:
        m = MockMigrator()
        self.assertEqual(m.min_version, Version(m._VERSION))  # noqa: SLF001

    def test_modify_column(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)
        m = migrations.SchemaMigrator(set())

        today = datetime.datetime.now().astimezone().date()

        with p.begin_session() as s:
            a_name = self.random_string()
            a = Asset(name=a_name, category=AssetCategory.ITEM)
            s.add(a)
            s.flush()

            v = AssetValuation(
                asset_id=a.id_,
                date_ord=today.toordinal(),
                value=self.random_decimal(1, 10),
            )
            s.add(v)

        with p.begin_session() as s:
            m.drop_column(s, Asset, "category")
            self.assertEqual(m.pending_schema_updates, set())

        with p.begin_session() as s:
            result = "\n".join(dump_table_configs(s, Asset))
            self.assertNotIn("category", result)

        with p.begin_session() as s:
            # value has constraints on it that must go first
            m.drop_column(s, AssetValuation, "value")
            self.assertEqual(m.pending_schema_updates, {AssetValuation})

        with p.begin_session() as s:
            result = "\n".join(dump_table_configs(s, AssetValuation))
            self.assertNotIn("value", result)

        # Add them back
        with p.begin_session() as s:
            m.add_column(s, Asset, Asset.category)
            m.add_column(s, AssetValuation, AssetValuation.value, Decimal(0))
            self.assertEqual(m.pending_schema_updates, {Asset, AssetValuation})

        # value got an initial value
        with p.begin_session() as s:
            v = s.query(AssetValuation.value).scalar()
            self.assertEqual(v, Decimal(0))

            # value can be negative because schemas not updated
            s.query(AssetValuation).update({"value": Decimal(-1)})
            s.query(AssetValuation).update({"value": Decimal(1)})

            v = s.query(Asset.category).where(Asset.name == a_name).scalar()
            self.assertIsNone(v)

            s.query(Asset).update({"category": AssetCategory.CASH})

        # Update schemas
        m.migrate(p)

        with p.begin_session() as s:
            # value can not be negative because schemas updated
            self.assertRaises(
                exc.IntegrityError,
                s.query(AssetValuation).update,
                {"value": Decimal(-1)},
            )

        with p.begin_session() as s:
            m.rename_column(s, Asset, "category", "class")

        with p.begin_session() as s:
            result = "\n".join(dump_table_configs(s, Asset))
            self.assertNotIn("category", result)
            self.assertIn("class", result)
