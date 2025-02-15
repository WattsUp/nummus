"""Migrate portfolio."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus.commands.base import Base

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class Migrate(Base):
    """Migrate portfolio."""

    NAME = "migrate"
    HELP = "migrate portfolio"
    DESCRIPTION = "Migrate portfolio to latest version"

    def __init__(self, path_db: Path, path_password: Path | None) -> None:
        """Initize migrate command.

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
        from nummus import exceptions as exc
        from nummus import portfolio
        from nummus.migrations import MIGRATORS

        p = self._p
        if p is None:  # pragma: no cover
            msg = "Portfolio is None"
            raise ValueError(msg)

        # Back up Portfolio
        _, tar_ver = p.backup()

        v_db = p.db_version

        for m_class in MIGRATORS:
            m_v = m_class.min_version
            if v_db >= m_v:
                continue
            try:
                m = m_class()
                m.migrate(p)

                print(f"{Fore.GREEN}Portfolio migrated to v{m_v}")
            except Exception as e:
                portfolio.Portfolio.restore(p, tar_ver=tar_ver)
                print(f"{Fore.RED}Abandoned migrate to v{m_v}, restored from backup")
                raise exc.FailedCommandError(self.NAME) from e

        return 0
