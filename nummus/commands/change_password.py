"""Change portfolio password."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus.commands.base import Base

if TYPE_CHECKING:
    import argparse


class ChangePassword(Base):
    """Change portfolio password."""

    NAME = "change-password"
    HELP = "change portfolio password"
    DESCRIPTION = "Change database and/or web password"

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        # No arguments
        _ = parser

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus import portfolio, utils

        if self._p is None:  # pragma: no cover
            return 1

        new_db_key: str | None = None
        change_db_key = utils.confirm("Change portfolio password?")
        if change_db_key:
            new_db_key = utils.get_password()
            if new_db_key is None:
                # Canceled
                return -1

        new_web_key: str | None = None
        change_web_key = False
        if self._p.is_encrypted or change_db_key:
            change_web_key = utils.confirm("Change web password?")
            if change_web_key:
                new_web_key = utils.get_password()
                if new_web_key is None:
                    # Canceled
                    return -1

        if not change_db_key and not change_web_key:
            print(f"{Fore.YELLOW}Neither password changing")
            return -1

        # Back up Portfolio
        _, tar_ver = self._p.backup()
        success = False

        try:
            if change_db_key and new_db_key is not None:
                self._p.change_key(new_db_key)

            if change_web_key and new_web_key is not None:
                self._p.change_web_key(new_web_key)

            success = True
        finally:
            # Restore backup if anything went wrong
            # Coverage gets confused with finally blocks
            if not success:  # pragma: no cover
                portfolio.Portfolio.restore(self._p, tar_ver=tar_ver)
                print(f"{Fore.RED}Abandoned password change, restored from backup")
        print(f"{Fore.GREEN}Changed password(s)")
        print(f"{Fore.CYAN}Run 'nummus clean' to remove backups with old password")
        return 0
