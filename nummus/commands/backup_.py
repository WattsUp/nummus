"""Backup and restore a portfolio."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from colorama import Fore

from nummus import portfolio, utils
from nummus.commands.unlock_ import unlock

if TYPE_CHECKING:
    from pathlib import Path


def backup(p: portfolio.Portfolio) -> int:
    """Backup portfolio to tar.gz.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    backup_tar, _ = p.backup()
    print(f"{Fore.GREEN}Portfolio backed up to {backup_tar}")
    return 0


def restore(
    path_db: Path,
    path_password: Path | None,
    tar_ver: int | None = None,
    *_,
    list_ver: bool = False,
) -> int:
    """Backup portfolio to tar.gz.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary
        tar_ver: Backup tar version to restore from, None will restore latest
        list_ver: True will list backups available, False will restore

    Returns:
        0 on success
        non-zero on failure
    """
    try:
        if list_ver:
            backups = portfolio.Portfolio.backups(path_db)
            if len(backups) == 0:
                print(f"{Fore.RED}No backups found, run nummus backup")
                return 0
            now = datetime.datetime.now(datetime.timezone.utc)
            for ver, ts in backups:
                ago_s = (now - ts).total_seconds()
                ago = utils.format_seconds(ago_s)

                # Convert ts utc to local timezone
                ts_local = ts.astimezone()
                print(
                    f"{Fore.CYAN}Backup #{ver:2} created at "
                    f"{ts_local.isoformat(timespec='seconds')} ({ago} ago)",
                )
            return 0
        portfolio.Portfolio.restore(path_db, tar_ver=tar_ver)
        print(f"{Fore.CYAN}Extracted backup tar.gz")
    except FileNotFoundError as e:
        print(f"{Fore.RED}{e}")
        return -1
    p = unlock(path_db, path_password)
    print(f"{Fore.GREEN}Portfolio restored for {p and p.path}")
    return 0
