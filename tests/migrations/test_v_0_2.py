from __future__ import annotations

import shutil

from nummus import portfolio
from nummus.migrations.v_0_2 import MigratorV0_2
from nummus.models import dump_table_configs, Transaction, TransactionSplit
from tests.base import TestBase


class TestMigratorV0_2(TestBase):  # noqa: N801

    def test_migrate(self) -> None:
        path_original = self._DATA_ROOT.joinpath("old_versions/v0.1.16.db")
        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        shutil.copyfile(path_original, path_db)

        p = portfolio.Portfolio(path_db, None, check_migration=False)
        m = MigratorV0_2()
        result = m.migrate(p)
        target = [
            "This transaction had multiple payees, only one allowed: "
            "1948-03-15 Savings, please validate",
        ]
        self.assertEqual(result, target)

        with p.begin_session() as s:
            result = "\n".join(dump_table_configs(s, Transaction))
            self.assertNotIn("linked", result)
            self.assertNotIn("locked", result)
            self.assertIn("cleared", result)
            self.assertIn("payee", result)

            result = "\n".join(dump_table_configs(s, TransactionSplit))
            self.assertNotIn("linked", result)
            self.assertNotIn("locked", result)
            # description is in name of check constraint until schema updates
            # Make sure it will be updated
            self.assertIn(TransactionSplit, m.pending_schema_updates)
            self.assertIn("cleared", result)
            self.assertIn("memo", result)
