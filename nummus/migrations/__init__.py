"""Migration handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.migrations.v_0_2 import MigratorV0_2

if TYPE_CHECKING:
    from nummus.migrations.base import Migrator

MIGRATORS: list[type[Migrator]] = [
    MigratorV0_2,
]
