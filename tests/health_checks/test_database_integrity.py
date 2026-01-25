from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import sqlalchemy

from nummus import sql
from nummus.health_checks.database_integrity import DatabaseIntegrity
from nummus.models.config import Config
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_empty() -> None:
    c = DatabaseIntegrity()
    c.test()
    assert c.issues == {}


def test_corrupt(session: orm.Session) -> None:
    n = Config.query().update({"value": "abc"})
    # Simulating a corrupt database is difficult
    # Instead update the Account schema to have unique constraint
    # PRAGMA integrity_check should catch duplicates
    index_name = f"{Config.__tablename__}_99"
    index_loc = f"{Config.__tablename__}({Config.value.key})"

    # Need to sneakily create unique constraint...
    query = f"CREATE INDEX {index_name} ON {index_loc};"
    session.execute(sqlalchemy.text(query))

    query = "PRAGMA writable_schema = 1;"
    session.execute(sqlalchemy.text(query))

    query = textwrap.dedent(
        f"""\
        UPDATE sqlite_master
            SET sql = 'CREATE UNIQUE INDEX {index_name} ON {index_loc}'
            WHERE type = 'index' AND name = '{index_name}';""",
    )
    session.execute(sqlalchemy.text(query))
    session.commit()

    c = DatabaseIntegrity()
    c.test()

    assert sql.count(HealthCheckIssue.query()) == n - 1

    i = HealthCheckIssue.first()
    assert i is not None
    assert i.check == c.name()
    assert i.value == "0"

    # The balanced $100 transfer also on this day will not show up
    target = {
        i.uri: f"non-unique entry in index {index_name}" for i in HealthCheckIssue.all()
    }
    assert c.issues == target
