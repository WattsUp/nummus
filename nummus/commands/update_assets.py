"""Update asset valuations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus.commands.base import Base

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class UpdateAssets(Base):
    """Update valuations for assets."""

    NAME = "update-assets"
    HELP = "update valuations for assets"
    DESCRIPTION = "Update asset valuations aka download market data for stocks"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
    ) -> None:
        """Initize update-assets command.

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
        # Defer for faster time to main
        from nummus import exceptions as exc
        from nummus import portfolio

        p = self._p
        if p is None:  # pragma: no cover
            return 1
        # Back up Portfolio
        _, tar_ver = p.backup()

        try:
            updated = p.update_assets()
        except Exception as e:
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned update assets, restored from backup")
            raise exc.FailedCommandError(self.NAME) from e

        if len(updated) == 0:
            print(
                f"{Fore.YELLOW}No assets were updated, "
                "add a ticker to an Asset to download market data",
            )
            return -2

        updated = sorted(updated, key=lambda item: item[0].lower())  # sort by name
        name_len = max(len(item[0]) for item in updated)
        ticker_len = max(len(item[1]) for item in updated)
        failed = False
        for name, ticker, start, end, error in updated:
            if start is None:
                print(
                    f"{Fore.RED}Asset {name:{name_len}} ({ticker:{ticker_len}}) "
                    f"failed to update. Error: {error}",
                )
                failed = True
            else:
                print(
                    f"{Fore.GREEN}Asset {name:{name_len}} ({ticker:{ticker_len}}) "
                    f"updated from {start} to {end}",
                )
        return 1 if failed else 0
