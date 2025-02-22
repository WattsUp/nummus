"""Base Migrator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import packaging.version
import sqlalchemy
from sqlalchemy import orm, sql

from nummus.models import Base, Config, ConfigKey
from nummus.utils import classproperty

if TYPE_CHECKING:
    from nummus import portfolio


class Migrator(ABC):
    """Base Migrator."""

    _VERSION: str

    @abstractmethod
    def migrate(self, p: portfolio.Portfolio) -> None:
        """Run migration.

        Args:
            p: Portfolio to migrate
        """

    @classproperty
    def min_version(self) -> packaging.version.Version:
        """Minimum version that satisfies migrator."""
        return packaging.version.Version(self._VERSION)

    def update_db_version(self, p: portfolio.Portfolio) -> None:
        """Update DB version.

        Args:
            p: Portfolio to update
        """
        with p.begin_session() as s:
            s.query(Config).where(Config.key == ConfigKey.VERSION).update(
                {"value": self._VERSION},
            )

    def add_column(
        self,
        s: orm.Session,
        model: type[Base],
        column: orm.QueryableAttribute,
        initial_value: object | None = None,
    ) -> None:
        """Add a column to a table.

        Args:
            s: SQL session to use
            model: Table to modify
            column: Column to add
            initial_value: Value to set all rows to
        """
        engine = s.get_bind().engine

        col_name = column.name
        col_type = column.type.compile(dialect=engine.dialect)
        stmt = f"ALTER TABLE '{model.__tablename__}' ADD COLUMN {col_name} {col_type}"
        s.execute(sqlalchemy.text(stmt))

        if initial_value is not None:
            s.query(model).update({column: initial_value})

    def migrate_schemas(
        self,
        s: orm.Session,
        model: type[Base],
    ) -> None:
        """Migrate the schemas of a table.

        Args:
            s: SQL session to use
            model: Table to modify
        """
        # In SQLite we can do the hacky way or recreate the table
        # Opt for recreate
        table: sqlalchemy.Table = model.__table__  # type: ignore[attr-defined]
        name = model.__tablename__

        # Turn on legacy_alter_table so renaming doesn't rename references
        stmt = "PRAGMA legacy_alter_table = ON"
        s.execute(sqlalchemy.text(stmt))

        stmt = f"ALTER TABLE '{name}' RENAME TO migration_temp"
        s.execute(sqlalchemy.text(stmt))

        # Reset it
        stmt = "PRAGMA legacy_alter_table = OFF"
        s.execute(sqlalchemy.text(stmt))

        table.create(bind=s.get_bind())

        columns = ", ".join(
            f"`{c.name}`" if c.name in sql.compiler.RESERVED_WORDS else c.name
            for c in table.columns
        )
        stmt = f"INSERT INTO '{name}' ({columns}) SELECT {columns} FROM migration_temp"  # noqa: S608
        s.execute(sqlalchemy.text(stmt))

        stmt = "DROP TABLE migration_temp"
        s.execute(sqlalchemy.text(stmt))
