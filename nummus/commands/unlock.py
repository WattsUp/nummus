"""Unlock a portfolio command."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class Unlock(BaseCommand):
    """Test unlocking portfolio."""

    NAME = "unlock"
    HELP = "test unlocking portfolio"
    DESCRIPTION = "Test unlocking portfolio"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
    ) -> None:
        """Initialize unlock command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary

        """
        super().__init__(path_db, path_password)

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        # No arguments
        _ = parser

    @override
    def run(self) -> int:
        return 0
