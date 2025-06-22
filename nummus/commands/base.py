"""Base command interface."""

from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from colorama import Fore

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from nummus.portfolio import Portfolio


class BaseCommand(ABC):
    """Base command interface."""

    NAME: str = ""
    HELP: str = ""
    DESCRIPTION: str = ""

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        *,
        do_unlock: bool = True,
        check_migration: bool = True,
    ) -> None:
        """Initize base command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            do_unlock: True will unlock portfolio, False will not
            check_migration: True will check if migration is required
        """
        super().__init__()

        path_db = path_db.expanduser().absolute()
        if path_password:
            path_password = path_password.expanduser().absolute()

        self._path_db = path_db
        self._path_password = path_password
        self._p: Portfolio | None = None

        # Defer for faster time to main
        from nummus import exceptions as exc  # noqa: PLC0415

        if do_unlock:
            try:
                self._p = unlock(
                    path_db,
                    path_password,
                    check_migration=check_migration,
                )
            except exc.MigrationRequiredError as e:
                print(f"{Fore.RED}{e}")
                print(f"{Fore.YELLOW}Run nummus migrate to resolve")
                sys.exit(1)

    @classmethod
    @abstractmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        """Setup subparser for this command.

        Args:
            parser: Subparser to add args to
        """
        raise NotImplementedError

    @abstractmethod
    def run(self) -> int:
        """Run command.

        Returns:
            0 on success
            non-zero on failure
        """
        raise NotImplementedError


def unlock(
    path_db: Path,
    path_password: Path | None,
    *,
    check_migration: bool = True,
) -> Portfolio | None:
    """Unlock an existing Portfolio.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary
        check_migration: True will check if migration is required

    Returns:
        Unlocked Portfolio or None if unlocking failed
    """
    # defer for faster time to main
    from nummus import exceptions as exc  # noqa: PLC0415
    from nummus import portfolio, utils  # noqa: PLC0415

    if not path_db.exists():
        print(f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create")
        return None

    if not portfolio.Portfolio.is_encrypted_path(path_db):
        p = portfolio.Portfolio(path_db, None, check_migration=check_migration)
        print(f"{Fore.GREEN}Portfolio is unlocked")
        return p

    key: str | None = None

    if path_password is not None and path_password.exists():
        with path_password.open(encoding="utf-8") as file:
            key = file.read().strip()

    if key is not None:
        # Try once with password file
        try:
            p = portfolio.Portfolio(path_db, key, check_migration=check_migration)
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
            p = portfolio.Portfolio(path_db, key, check_migration=check_migration)
        except exc.UnlockingError:
            print(f"{Fore.RED}Incorrect password")
            # Try again
        else:
            print(f"{Fore.GREEN}Portfolio is unlocked")
            return p

    print(f"{Fore.RED}Too many incorrect attempts")
    return None
