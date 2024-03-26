"""Create a portfolio command."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus.commands.base import Base

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


MIN_PASS_LEN = 8


class Create(Base):
    """Create portfolio."""

    NAME = "create"
    HELP = "create nummus portfolio"
    DESCRIPTION = "Create a new nummus portfolio"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        *,
        force: bool,
        no_encrypt: bool,
    ) -> None:
        """Initize create command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            force: True will overwrite existing if necessary
            no_encrypt: True will not encrypt the Portfolio
        """
        super().__init__(path_db, path_password, do_unlock=False)
        self._force = force
        self._no_encrypt = no_encrypt

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--force",
            default=False,
            action="store_true",
            help="Force create a new portfolio, will overwrite existing",
        )
        parser.add_argument(
            "--no-encrypt",
            default=False,
            action="store_true",
            help="do not encrypt portfolio",
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus import portfolio, utils

        if self._path_db.exists():
            if self._force:
                self._path_db.unlink()
            else:
                print(
                    f"{Fore.RED}Cannot overwrite portfolio at {self._path_db}. "
                    "Try with --force",
                )
                return -1

        key: str | None = None
        if not self._no_encrypt:
            if self._path_password is not None and self._path_password.exists():
                with self._path_password.open(encoding="utf-8") as file:
                    key = file.read().strip()

            # Get key from user is password file empty

            # Prompt user
            while key is None:
                key = utils.get_input("Please enter password: ", secure=True)
                if key is None:
                    return -1

                if len(key) < MIN_PASS_LEN:
                    print(
                        f"{Fore.RED}Password must be at least {MIN_PASS_LEN} "
                        "characters",
                    )
                    key = None
                    continue

                repeat = utils.get_input("Please confirm password: ", secure=True)
                if repeat is None:
                    return -1

                if key != repeat:
                    print(f"{Fore.RED}Passwords must match")
                    key = None

        portfolio.Portfolio.create(self._path_db, key)
        print(f"{Fore.GREEN}Portfolio created at {self._path_db}")

        return 0
