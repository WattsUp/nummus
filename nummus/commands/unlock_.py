"""Unlock a portfolio command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus import exceptions as exc
from nummus import portfolio, utils

if TYPE_CHECKING:
    from pathlib import Path


def unlock(path_db: Path, path_password: Path | None) -> portfolio.Portfolio | None:
    """Unlock an existing Portfolio.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary

    Returns:
        Unlocked Portfolio or None if unlocking failed
    """
    if not path_db.exists():
        print(f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create")
        return None

    if not portfolio.Portfolio.is_encrypted(path_db):
        p = portfolio.Portfolio(path_db, None)
        print(f"{Fore.GREEN}Portfolio is unlocked")
        return p

    key: str | None = None

    if path_password is not None and path_password.exists():
        with path_password.open(encoding="utf-8") as file:
            key = file.read().strip()

    if key is not None:
        # Try once with password file
        try:
            p = portfolio.Portfolio(path_db, key)
        except exc.UnlockingError:
            print(f"{Fore.RED}Could not decrypt with password file")
            return None
        else:
            print(f"{Fore.GREEN}Portfolio is unlocked")
            return p

    # 3 attempts
    for _ in range(3):
        key = utils.get_input("Please enter password: ", secure=True)
        if key is None:
            return None
        try:
            p = portfolio.Portfolio(path_db, key)
        except exc.UnlockingError:
            print(f"{Fore.RED}Incorrect password")
            # Try again
        else:
            print(f"{Fore.GREEN}Portfolio is unlocked")
            return p

    print(f"{Fore.RED}Too many incorrect attempts")
    return None
