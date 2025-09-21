"""Summarize a portfolio and print."""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import override, TYPE_CHECKING, TypedDict

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class _AccountSummary(TypedDict):
    """Type annotation for summarize."""

    name: str
    institution: str
    category: str
    value: Decimal
    age: str
    profit: Decimal


class _AssetSummary(TypedDict):
    """Type annotation for summarize."""

    name: str
    description: str | None
    value: Decimal
    profit: Decimal
    category: str
    ticker: str | None


class _Summary(TypedDict):
    """Type annotation for summarize."""

    n_accounts: int
    n_assets: int
    n_transactions: int
    n_valuations: int
    net_worth: Decimal
    accounts: list[_AccountSummary]
    total_asset_value: Decimal
    assets: list[_AssetSummary]
    db_size: int


class Summarize(BaseCommand):
    """Print summary information and statistics on Portfolio."""

    NAME = "summarize"
    HELP = "summarize portfolio"
    DESCRIPTION = "Collect statistics and print a summary of the portfolio"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        *,
        include_all: bool,
    ) -> None:
        """Initialize summarize command.

        Args:
            path_db: Path to Portfolio DB to create
            path_password: Path to password file, None will prompt when necessary
            include_all: True will include all accounts and assets

        """
        super().__init__(path_db, path_password)
        self._include_all = include_all

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-a",
            "--include-all",
            default=False,
            action="store_true",
            help="include all accounts assets",
        )

    @override
    def run(self) -> int:
        summary = self._get_summary()
        self._print_summary(summary)
        return 0

    def _get_summary(
        self,
    ) -> _Summary:
        """Summarize Portfolio into useful information and statistics.

        Returns:
            Dictionary of statistics

        """
        # Defer for faster time to main
        from sqlalchemy import func

        from nummus import utils
        from nummus.models import (
            Account,
            Asset,
            AssetCategory,
            AssetValuation,
            query_count,
            TransactionSplit,
        )

        today = datetime.datetime.now().astimezone().date()
        today_ord = today.toordinal()

        with self._p.begin_session() as s:
            accts = {acct.id_: acct for acct in s.query(Account).all()}
            assets = {
                a.id_: a
                for a in (
                    s.query(Asset).where(Asset.category != AssetCategory.INDEX).all()
                )
            }

            # Get the inception date
            start_date_ord: int = (
                s.query(
                    func.min(TransactionSplit.date_ord),
                ).scalar()
                or datetime.date(1970, 1, 1).toordinal()
            )

            n_accounts = len(accts)
            n_transactions = query_count(s.query(TransactionSplit))
            n_assets = len(assets)
            n_valuations = query_count(s.query(AssetValuation))

            value_accts, profit_accts, value_assets = Account.get_value_all(
                s,
                start_date_ord,
                today_ord,
            )

            net_worth = Decimal()
            summary_accts: list[_AccountSummary] = []
            for acct_id, acct in accts.items():
                if not self._include_all and acct.closed:
                    continue

                v = value_accts[acct_id][-1]
                profit = profit_accts[acct_id][-1]
                net_worth += v
                summary_accts.append(
                    {
                        "name": acct.name,
                        "institution": acct.institution,
                        "category": acct.category.name.replace("_", " ").capitalize(),
                        "value": v,
                        "age": utils.format_days(
                            today_ord - (acct.opened_on_ord or today_ord),
                        ),
                        "profit": profit,
                    },
                )

            summary_accts = sorted(
                summary_accts,
                key=lambda item: (
                    -item["value"],
                    -item["profit"],
                    item["name"].lower(),
                ),
            )

            profit_assets = Account.get_profit_by_asset_all(
                s,
                start_date_ord,
                today_ord,
            )

            total_asset_value = Decimal()
            summary_assets: list[_AssetSummary] = []
            for a_id, a in assets.items():
                v = value_assets[a_id][-1]
                if not self._include_all and v == 0:
                    continue

                profit = profit_assets[a_id]
                total_asset_value += v
                summary_assets.append(
                    {
                        "name": a.name,
                        "description": a.description,
                        "ticker": a.ticker,
                        "category": a.category.name.replace("_", " ").capitalize(),
                        "value": v,
                        "profit": profit,
                    },
                )
            summary_assets = sorted(
                summary_assets,
                key=lambda item: (
                    -item["value"],
                    -item["profit"],
                    item["name"].lower(),
                ),
            )
        return {
            "n_accounts": n_accounts,
            "n_assets": n_assets,
            "n_transactions": n_transactions,
            "n_valuations": n_valuations,
            "net_worth": net_worth,
            "accounts": summary_accts,
            "total_asset_value": total_asset_value,
            "assets": summary_assets,
            "db_size": self._p.path.stat().st_size,
        }

    @classmethod
    def _print_summary(cls, summary: _Summary) -> None:
        """Print summary statistics as a pretty table.

        Args:
            summary: Summary dictionary

        """
        # Defer for faster time to main
        from nummus import utils

        def is_are(i: int) -> str:
            return "is" if i == 1 else "are"

        def plural(i: int) -> str:
            return "" if i == 1 else "s"

        size: int = summary["db_size"]
        print(f"Portfolio file size is {size / 1000:,.1f}KB/{size / 1024:,.1f}KiB")

        # Accounts
        table: list[list[str] | None] = [
            [
                "Name",
                "Institution.",
                "Category",
                ">Value/",
                ">Profit/",
                ">Age/",
            ],
            None,
        ]
        table.extend(
            [
                acct["name"],
                acct["institution"],
                acct["category"],
                utils.format_financial(acct["value"]),
                utils.format_financial(acct["profit"]),
                acct["age"],
            ]
            for acct in summary["accounts"]
        )
        table.extend(
            (
                None,
                [
                    "Total",
                    "",
                    "",
                    utils.format_financial(summary["net_worth"]),
                    "",
                    "",
                ],
            ),
        )
        n = summary["n_accounts"]
        n_table = len(summary["accounts"])
        print(
            f"There {is_are(n)} {n:,} account{plural(n)}, "
            f"{n_table:,} of which {is_are(n_table)} currently open",
        )
        print("\n".join(utils.pretty_table(table)))

        # Assets
        table = [
            [
                "Name",
                "Description.",
                "Class",
                "Ticker",
                ">Value/",
                ">Profit/",
            ],
            None,
        ]
        table.extend(
            [
                asset["name"],
                asset["description"] or "",
                asset["category"],
                asset["ticker"] or "",
                utils.format_financial(asset["value"]),
                utils.format_financial(asset["profit"]),
            ]
            for asset in summary["assets"]
        )
        table.append(None)
        table.append(
            [
                "Total",
                "",
                "",
                "",
                utils.format_financial(summary["total_asset_value"]),
                "",
            ],
        )
        n = summary["n_assets"]
        n_table = len(summary["assets"])
        print(
            f"There {is_are(n)} {n:,} asset{plural(n)}, "
            f"{n_table:,} of which {is_are(n_table)} currently held",
        )
        print("\n".join(utils.pretty_table(table)))

        n = summary["n_valuations"]
        print(f"There {is_are(n)} {n:,} asset valuation{plural(n)}")

        n = summary["n_transactions"]
        print(f"There {is_are(n)} {n:,} transaction{plural(n)}")
