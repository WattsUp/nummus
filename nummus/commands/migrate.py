"""Migrate portfolio."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from colorama import Fore

from nummus.commands.base import Command
from nummus.version import __version__

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from nummus.models.base import Base


class Migrate(Command):
    """Migrate portfolio."""

    NAME = "migrate"
    HELP = "migrate portfolio"
    DESCRIPTION = "Migrate portfolio to latest version"

    def __init__(self, path_db: Path, path_password: Path | None) -> None:
        """Initialize migrate command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary

        """
        super().__init__(path_db, path_password, check_migration=False)

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        # No arguments
        _ = parser

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from packaging.version import Version

        from nummus import portfolio
        from nummus.migrations.base import SchemaMigrator
        from nummus.migrations.top import MIGRATORS
        from nummus.models.config import Config, ConfigKey

        p = self._p

        # Back up Portfolio
        _, tar_ver = p.backup()

        with p.begin_session() as s:
            v_db = Config.db_version(s)

        any_migrated = False
        try:
            pending_schema_updates: set[type[Base]] = set()
            for m_class in MIGRATORS:
                v_m = m_class.min_version()
                if v_db >= v_m:
                    continue
                m = m_class()
                any_migrated = True
                comments = m.migrate(p)
                for line in comments:
                    print(f"{Fore.CYAN}{line}")

                print(f"{Fore.GREEN}Portfolio migrated to v{v_m}")
                pending_schema_updates.update(m.pending_schema_updates)

            if pending_schema_updates:
                m = SchemaMigrator(pending_schema_updates)
                m.migrate(p)  # no comments
                print(f"{Fore.GREEN}Portfolio model schemas updated")

            with p.begin_session() as s:
                v = max(
                    Version(__version__),
                    *[m.min_version() for m in MIGRATORS],
                )

                Config.set_(s, ConfigKey.VERSION, str(v))
        except Exception:  # pragma: no cover
            # No immediate exception thrown, can't easily test
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned migrate, restored from backup")
            raise

        if not any_migrated:
            print(f"{Fore.GREEN}Portfolio does not need migration")

        return 0
