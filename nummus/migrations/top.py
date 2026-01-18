"""Migrators."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.migrations.v0_2 import MigratorV0_2
from nummus.migrations.v0_10 import MigratorV0_10
from nummus.migrations.v0_11 import MigratorV0_11
from nummus.migrations.v0_13 import MigratorV0_13
from nummus.migrations.v0_15 import MigratorV0_15
from nummus.migrations.v0_16 import MigratorV0_16

if TYPE_CHECKING:
    from nummus.migrations.base import Migrator

MIGRATORS: list[type[Migrator]] = [
    MigratorV0_2,
    MigratorV0_10,
    MigratorV0_11,
    MigratorV0_13,
    MigratorV0_15,
    MigratorV0_16,
]
