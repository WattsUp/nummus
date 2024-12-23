from __future__ import annotations

import secrets

import sqlalchemy
from pandas.core.indexes.api import textwrap

from nummus import portfolio
from nummus.health_checks.database_integrity import DatabaseIntegrity
from nummus.models import Account, AccountCategory, HealthCheckIssue
from tests.base import TestBase


class TestDatabaseIntegrity(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        c = DatabaseIntegrity(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            acct_savings = Account(
                name="Monkey Bank Savings",
                institution="Monkey Bank",
                category=AccountCategory.CREDIT,
                closed=False,
                budgeted=True,
            )
            s.add_all((acct_checking, acct_savings))

        c = DatabaseIntegrity(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        # Simulating a corrupt database is difficult
        # Instead update the Account schema to have unique constraint
        # PRAGMA integrity_check should catch duplicates
        with p.begin_session() as s:
            index_name = f"{Account.__tablename__}_99"
            index_loc = f"{Account.__tablename__}({Account.institution.key})"

            # Need to sneakily create unique constraint...
            query = f"CREATE INDEX {index_name} ON {index_loc};"
            s.execute(sqlalchemy.text(query))

            query = "PRAGMA writable_schema = 1;"
            s.execute(sqlalchemy.text(query))

            query = textwrap.dedent(
                f"""\
                UPDATE sqlite_master
                    SET sql = 'CREATE UNIQUE INDEX {index_name} ON {index_loc}'
                    WHERE type = 'index' AND name = '{index_name}';""",
            )
            s.execute(sqlalchemy.text(query))

        c = DatabaseIntegrity(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, "0")
            uri = i.uri

        # The balanced $100 transfer also on this day will not show up
        target = {
            uri: f"non-unique entry in index {index_name}",
        }
        self.assertEqual(c.issues, target)
