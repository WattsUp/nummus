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
        """Initialize base command.

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

        # Defer for faster time to main
        from nummus import exceptions as exc

        if not do_unlock:
            return

        if not path_db.exists():
            print(
                f"{Fore.RED}Portfolio does not exist at {path_db}. "
                "Run nummus create",
                file=sys.stderr,
            )
            sys.exit(1)
        key: str | None = None
        if path_password is not None and path_password.exists():
            with path_password.open(encoding="utf-8") as file:
                key = file.read().strip()

        try:
            self._p = self._unlock(
                path_db,
                key,
                check_migration=check_migration,
            )
        except exc.MigrationRequiredError as e:
            print(f"{Fore.RED}{e}", file=sys.stderr)
            print(f"{Fore.YELLOW}Run 'nummus migrate' to resolve", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"{Fore.GREEN}Portfolio is unlocked")

    @classmethod
    @abstractmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        """Set up subparser for this command.

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

    @classmethod
    def _unlock(
        cls,
        path_db: Path,
        key: str | None,
        *,
        check_migration: bool = True,
    ) -> Portfolio:
        """Unlock an existing Portfolio.

        Args:
            path_db: Path to Portfolio DB to unlock
            key: Portfolio key, None will prompt when necessary
            check_migration: True will check if migration is required

        Returns:
            Unlocked Portfolio

        """
        # defer for faster time to main
        from nummus import exceptions as exc
        from nummus import portfolio, utils

        if not portfolio.Portfolio.is_encrypted_path(path_db):
            return portfolio.Portfolio(path_db, None, check_migration=check_migration)

        if key is not None:
            # Try once with password file
            try:
                p = portfolio.Portfolio(path_db, key, check_migration=check_migration)
            except exc.UnlockingError:
                print(
                    f"{Fore.RED}Could not decrypt with password file",
                    file=sys.stderr,
                )
                sys.exit(1)
            else:
                return p

        # 3 attempts
        for _ in range(3):
            key = utils.get_input("Please enter password: ", secure=True)
            if key is None:
                sys.exit(1)
            try:
                p = portfolio.Portfolio(path_db, key, check_migration=check_migration)
            except exc.UnlockingError:
                print(f"{Fore.RED}Incorrect password", file=sys.stderr)
                # Try again
            else:
                return p

        print(f"{Fore.RED}Too many incorrect attempts", file=sys.stderr)
        sys.exit(1)
