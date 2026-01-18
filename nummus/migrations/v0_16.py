"""Migrator to v0.16.0."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.migrations.base import Migrator
from nummus.models.account import Account
from nummus.models.asset import Asset
from nummus.models.config import Config, ConfigKey
from nummus.models.currency import DEFAULT_CURRENCY

if TYPE_CHECKING:
    from nummus import portfolio


class MigratorV0_16(Migrator):
    """Migrator to v0.16.0."""

    _VERSION = "0.16.0"

    @override
    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        _ = p

        comments: list[str] = [
            f"Portfolio currency set to {DEFAULT_CURRENCY.pretty}, use web to edit",
        ]

        with p.begin_session() as s:
            s.add(
                Config(key=ConfigKey.BASE_CURRENCY, value=str(DEFAULT_CURRENCY.value)),
            )

            self.add_column(s, Account, Account.currency, DEFAULT_CURRENCY)
            self.add_column(s, Asset, Asset.currency, DEFAULT_CURRENCY)

        return comments
