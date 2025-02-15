"""Base Migrator."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import packaging.version

from nummus.models import Config, ConfigKey
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
