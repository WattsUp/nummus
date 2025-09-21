"""Backup and restore a portfolio."""

from __future__ import annotations

import datetime
import sys
from typing import override, TYPE_CHECKING

from colorama import Fore

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class Backup(BaseCommand):
    """Backup portfolio."""

    NAME = "backup"
    HELP = "backup portfolio"
    DESCRIPTION = "Backup portfolio to a tar"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
    ) -> None:
        """Initialize backup command.

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
        backup_tar, _ = self._p.backup()
        print(f"{Fore.GREEN}Portfolio backed up to {backup_tar}")
        return 0


class Restore(BaseCommand):
    """Restore portfolio from backup."""

    NAME = "restore"
    HELP = "restore portfolio from backup"
    DESCRIPTION = "Restore portfolio from backup"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        tar_ver: int | None,
        *,
        list_ver: bool,
    ) -> None:
        """Initialize restore command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            tar_ver: Backup tar version to restore from, None will restore latest
            list_ver: True will list backups available, False will restore

        """
        super().__init__(path_db, path_password, do_unlock=False)
        self._tar_ver = tar_ver
        self._list_ver = list_ver

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-v",
            dest="tar_ver",
            metavar="VERSION",
            type=int,
            help="number of backup to use for restore, omit for latest",
        )
        parser.add_argument(
            "-l",
            "--list",
            dest="list_ver",
            default=False,
            action="store_true",
            help="list available backups",
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus import portfolio, utils

        try:
            if self._list_ver:
                backups = portfolio.Portfolio.backups(self._path_db)
                if len(backups) == 0:
                    print(
                        f"{Fore.RED}No backups found, run 'nummus backup'",
                        file=sys.stderr,
                    )
                    return 0
                now = datetime.datetime.now(datetime.UTC)
                for ver, ts in backups:
                    ago_s = (now - ts).total_seconds()
                    ago = utils.format_seconds(ago_s)

                    # Convert ts utc to local timezone
                    ts_local = ts.astimezone().isoformat(timespec="seconds")
                    print(
                        f"{Fore.CYAN}Backup #{ver:2} created at {ts_local} ({ago} ago)",
                    )
                return 0
            portfolio.Portfolio.restore(self._path_db, tar_ver=self._tar_ver)
            print(f"{Fore.CYAN}Extracted backup tar")
        except FileNotFoundError as e:
            print(f"{Fore.RED}{e}", file=sys.stderr)
            return -1
        print(f"{Fore.GREEN}Portfolio restored for {self._path_db}")
        return 0
