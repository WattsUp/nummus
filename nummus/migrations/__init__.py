"""Migration handlers."""

from __future__ import annotations

from nummus.migrations.base import Migrator, SchemaMigrator
from nummus.migrations.v0_2 import MigratorV0_2
from nummus.migrations.v0_10 import MigratorV0_10

__all__ = [
    "MIGRATORS",
    "Migrator",
    "SchemaMigrator",
]

MIGRATORS: list[type[Migrator]] = [
    MigratorV0_2,
    MigratorV0_10,
]
