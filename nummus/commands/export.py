"""Export transactions to CSV."""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import override, TYPE_CHECKING

from colorama import Fore

from nummus.commands.base import Command

if TYPE_CHECKING:
    import argparse
    import io

    from sqlalchemy import orm

    from nummus.models.currency import Currency
    from nummus.models.transaction import TransactionSplit


class Export(Command):
    """Export transactions."""

    NAME = "export"
    HELP = "export transactions to a CSV"
    DESCRIPTION = "Export all transactions within a date to CSV"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        csv_path: Path,
        start: datetime.date | None,
        end: datetime.date | None,
        *,
        no_bars: bool,
    ) -> None:
        """Initialize export command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            csv_path: Path to CSV output
            start: Start date to filter transactions
            end: End date to filter transactions
            no_bars: True will disable progress bars

        """
        super().__init__(path_db, path_password)
        self._csv_path = csv_path
        self._start = start
        self._end = end
        self._no_bars = no_bars

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--start",
            metavar="YYYY-MM-DD",
            type=datetime.date.fromisoformat,
            help="date of first transaction to export",
        )
        parser.add_argument(
            "--end",
            metavar="YYYY-MM-DD",
            type=datetime.date.fromisoformat,
            help="date of last transaction to export",
        )
        parser.add_argument(
            "csv_path",
            metavar="CSV_PATH",
            type=Path,
            help="path to CSV file to export",
        )
        parser.add_argument(
            "--no-bars",
            default=False,
            action="store_true",
            help="disable progress bars",
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus.models.transaction import TransactionSplit

        with self._p.begin_session() as s:
            query = (
                s.query(TransactionSplit)
                .where(
                    TransactionSplit.asset_id.is_(None),
                )
                .with_entities(TransactionSplit.amount)
            )
            if self._start is not None:
                query = query.where(
                    TransactionSplit.date_ord >= self._start.toordinal(),
                )
            if self._end is not None:
                query = query.where(
                    TransactionSplit.date_ord <= self._end.toordinal(),
                )

            with self._csv_path.open("w", encoding="utf-8") as file:
                n = write_csv(file, query, no_bars=self._no_bars)
        print(f"{Fore.GREEN}{n} transactions exported to {self._csv_path}")
        return 0


def write_csv(
    file: io.TextIOBase,
    transactions_query: orm.Query[TransactionSplit],
    *,
    no_bars: bool,
) -> int:
    """Write transactions to CSV file.

    Args:
        file: Destination file to write to
        transactions_query: ORM query to obtain TransactionSplits
        no_bars: True will disable progress bars

    Returns:
        Number of transactions exported

    """
    # Defer for faster time to main
    import tqdm

    from nummus.models.account import Account
    from nummus.models.base import YIELD_PER
    from nummus.models.currency import CURRENCY_FORMATS
    from nummus.models.transaction import TransactionCategory, TransactionSplit
    from nummus.models.utils import query_count

    s = transactions_query.session

    query = s.query(Account).with_entities(
        Account.id_,
        Account.name,
        Account.currency,
    )
    accounts: dict[int, tuple[str, Currency]] = {
        r[0]: (r[1], r[2]) for r in query.yield_per(YIELD_PER)
    }

    categories = TransactionCategory.map_name_emoji(s)

    query = transactions_query.with_entities(
        TransactionSplit.date_ord,
        TransactionSplit.account_id,
        TransactionSplit.payee,
        TransactionSplit.memo,
        TransactionSplit.category_id,
        TransactionSplit.amount,
    ).order_by(TransactionSplit.date_ord)
    n = query_count(query)

    header = [
        "Date",
        "Account",
        "Payee",
        "Memo",
        "Category",
        "Amount",
    ]
    lines: list[list[str]] = []
    for (
        date,
        acct_id,
        payee,
        memo,
        t_cat_id,
        amount,
    ) in tqdm.tqdm(
        query.yield_per(YIELD_PER),
        total=n,
        desc="Exporting",
        disable=no_bars,
    ):
        acct_name, currency = accounts[acct_id]
        cf = CURRENCY_FORMATS[currency]

        lines.append(
            [
                datetime.date.fromordinal(date).isoformat(),
                acct_name,
                payee,
                memo,
                categories[t_cat_id],
                cf(amount),
            ],
        )

    writer = csv.writer(file)
    writer.writerow(header)
    writer.writerows(lines)
    return n
