"""Change portfolio password."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse


class ChangePassword(BaseCommand):
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
        from nummus import portfolio, utils  # noqa: PLC0415

        p = self._p

        new_db_key: str | None = None
        change_db_key = utils.confirm("Change portfolio password?")
        if change_db_key:
            new_db_key = utils.get_password()
            if new_db_key is None:
                # Canceled
                return -1

        new_web_key: str | None = None
        change_web_key = False
        if p.is_encrypted or change_db_key:
            change_web_key = utils.confirm("Change web password?")
            if change_web_key:
                new_web_key = utils.get_password()
                if new_web_key is None:
                    # Canceled
                    return -1

        if not change_db_key and not change_web_key:
            print(f"{Fore.YELLOW}Neither password changing", file=sys.stderr)
            return -1

        # Back up Portfolio
        _, tar_ver = p.backup()
        try:
            if change_db_key and new_db_key is not None:
                p.change_key(new_db_key)

            if change_web_key and new_web_key is not None:
                p.change_web_key(new_web_key)
        except Exception:  # pragma: no cover
            # No immediate exception thrown, can't easily test
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned password change, restored from backup")
            raise
        print(f"{Fore.GREEN}Changed password(s)")
        print(f"{Fore.CYAN}Run 'nummus clean' to remove backups with old password")
        return 0
