"""Migration handlers."""

from __future__ import annotations

from nummus.migrations.base import Migrator, SchemaMigrator
from nummus.migrations.v_0_2 import MigratorV0_2

__all__ = [
    "MIGRATORS",
    "Migrator",
    "MigratorV0_2",
    "SchemaMigrator",
]

MIGRATORS: list[type[Migrator]] = [
    MigratorV0_2,
]
