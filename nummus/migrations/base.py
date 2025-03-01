"""Base Migrator."""

from __future__ import annotations

import textwrap
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import packaging.version
import sqlalchemy
from sqlalchemy import orm

from nummus import sql
from nummus.models import Base, Config, ConfigKey
from nummus.utils import classproperty

if TYPE_CHECKING:
    from nummus import portfolio


class Migrator(ABC):
    """Base Migrator."""

    _VERSION: str

    @abstractmethod
    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        """Run migration.

        Args:
            p: Portfolio to migrate

        Returns:
            List of comments to display to user
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

        col_name = sql.escape(column.name)
        col_type = column.type.compile(dialect=engine.dialect)
        stmt = f'ALTER TABLE "{model.__tablename__}" ADD {col_name} {col_type}'
        s.execute(sqlalchemy.text(stmt))

        if initial_value is not None:
            s.query(model).update({column: initial_value})

    def rename_column(
        self,
        s: orm.Session,
        model: type[Base],
        old_name: str,
        new_name: str,
    ) -> None:
        """Rename a column in a table.

        Args:
            s: SQL session to use
            model: Table to modify
            old_name: Current name of column
            new_name: New name of column
        """
        old_name = sql.escape(old_name)
        new_name = sql.escape(new_name)
        stmt = f'ALTER TABLE "{model.__tablename__}" RENAME {old_name} TO {new_name}'
        s.execute(sqlalchemy.text(stmt))

    def drop_column(
        self,
        s: orm.Session,
        model: type[Base],
        col_name: str,
    ) -> None:
        """Rename a column in a table.

        Args:
            s: SQL session to use
            model: Table to modify
            col_name: Name of column to drop
        """
        col_name = sql.escape(col_name)
        stmt = f'ALTER TABLE "{model.__tablename__}" DROP {col_name}'
        s.execute(sqlalchemy.text(stmt))

    def migrate_schemas(
        self,
        s: orm.Session,
        model: type[Base],
        *,
        drop: set[str] | None = None,
    ) -> None:
        """Migrate the schemas of a table.

        Args:
            s: SQL session to use
            model: Table to modify
            drop: Set of column names to drop
        """
        drop = drop or set()
        # In SQLite we can do the hacky way or recreate the table
        # Opt for recreate
        table: sqlalchemy.Table = model.__table__  # type: ignore[attr-defined]
        name = model.__tablename__

        # Turn on legacy_alter_table so renaming doesn't rename references
        stmt = "PRAGMA foreign_keys = OFF"
        s.execute(sqlalchemy.text(stmt))
        stmt = "PRAGMA legacy_alter_table = ON"
        s.execute(sqlalchemy.text(stmt))

        stmt = f'ALTER TABLE "{name}" RENAME TO "migration_temp"'
        s.execute(sqlalchemy.text(stmt))

        # Reset
        stmt = "PRAGMA foreign_keys = ON"
        s.execute(sqlalchemy.text(stmt))
        stmt = "PRAGMA legacy_alter_table = OFF"
        s.execute(sqlalchemy.text(stmt))

        table.create(bind=s.get_bind())

        columns = ", ".join(
            sql.escape(c.name) for c in table.columns if c.name not in drop
        )
        stmt = textwrap.dedent(
            f"""\
            INSERT INTO "{name}" ({columns})
                SELECT {columns}
                FROM "migration_temp";""",  # noqa: S608
        )
        s.execute(sqlalchemy.text(stmt))

        stmt = 'DROP TABLE "migration_temp"'
        s.execute(sqlalchemy.text(stmt))
