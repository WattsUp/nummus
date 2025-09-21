"""Update asset valuations."""

from __future__ import annotations

import sys
from typing import override, TYPE_CHECKING

from colorama import Fore

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class UpdateAssets(BaseCommand):
    """Update valuations for assets."""

    NAME = "update-assets"
    HELP = "update valuations for assets"
    DESCRIPTION = "Update asset valuations aka download market data for stocks"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        *,
        no_bars: bool,
    ) -> None:
        """Initialize update-assets command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            no_bars: True will disable progress bars

        """
        super().__init__(path_db, path_password)
        self._no_bars = no_bars

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--no-bars",
            default=False,
            action="store_true",
            help="disable progress bars",
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus import portfolio

        p = self._p
        # Back up Portfolio
        _, tar_ver = p.backup()

        try:
            updated = p.update_assets(no_bars=self._no_bars)
        except Exception:  # pragma: no cover
            # No immediate exception thrown, can't easily test
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(
                f"{Fore.RED}Abandoned update assets, restored from backup",
                file=sys.stderr,
            )
            raise

        if len(updated) == 0:
            print(
                f"{Fore.YELLOW}No assets were updated, "
                "add a ticker to an Asset to download market data",
                file=sys.stderr,
            )
            return 0

        updated = sorted(updated, key=lambda item: item[0].lower())  # sort by name
        name_len = max(len(asset.name) for asset in updated)
        ticker_len = max(len(asset.ticker) for asset in updated)
        failed = False
        for asset in updated:
            if asset.start is None:
                print(
                    f"{Fore.RED}Asset {asset.name:{name_len}} "
                    f"({asset.ticker:{ticker_len}}) "
                    f"failed to update. Error: {asset.error}",
                    file=sys.stderr,
                )
                failed = True
            else:
                print(
                    f"{Fore.GREEN}Asset {asset.name:{name_len}} "
                    f"({asset.ticker:{ticker_len}}) "
                    f"updated from {asset.start} to {asset.end}",
                )
        return -1 if failed else 0
