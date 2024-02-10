"""Create a portfolio command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus import portfolio, utils

if TYPE_CHECKING:
    from pathlib import Path


MIN_PASS_LEN = 8


def create(
    path_db: Path,
    path_password: Path | None,
    *,
    force: bool,
    no_encrypt: bool,
) -> int:
    """Create a new Portfolio.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary
        force: True will overwrite existing if necessary
        no_encrypt: True will not encrypt the Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    if path_db.exists():
        if force:
            path_db.unlink()
        else:
            print(
                f"{Fore.RED}Cannot overwrite portfolio at {path_db}. Try with --force",
            )
            return -1

    key: str | None = None
    if not no_encrypt:
        if path_password is not None and path_password.exists():
            with path_password.open(encoding="utf-8") as file:
                key = file.read().strip()

        # Get key from user is password file empty

        # Prompt user
        while key is None:
            key = utils.get_input("Please enter password: ", secure=True)
            if key is None:
                return -1

            if len(key) < MIN_PASS_LEN:
                print(f"{Fore.RED}Password must be at least {MIN_PASS_LEN} characters")
                key = None
                continue

            repeat = utils.get_input("Please confirm password: ", secure=True)
            if repeat is None:
                return -1

            if key != repeat:
                print(f"{Fore.RED}Passwords must match")
                key = None

    portfolio.Portfolio.create(path_db, key)
    print(f"{Fore.GREEN}Portfolio created at {path_db}")

    return 0
