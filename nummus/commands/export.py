"""Export transactions to CSV."""

from __future__ import annotations

import csv
import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
    import io

    from sqlalchemy import orm

    from nummus.models import TransactionSplit


class Export(BaseCommand):
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
    ) -> None:
        """Initize export command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            csv_path: Path to CSV output
            start: Start date to filter transactions
            end: End date to filter transactions
        """
        super().__init__(path_db, path_password)
        self._csv_path = csv_path
        self._start = start
        self._end = end

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

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus.models import TransactionSplit  # noqa: PLC0415

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
                write_csv(file, query)
        return 0


def write_csv(
    file: io.TextIOBase,
    transactions_query: orm.Query[TransactionSplit],
) -> None:
    """Write transactions to CSV file.

    Args:
        file: Destination file to write to
        transactions_query: ORM query to obtain TransactionSplits
    """
    # Defer for faster time to main
    import tqdm  # noqa: PLC0415

    from nummus import utils  # noqa: PLC0415
    from nummus.models import (  # noqa: PLC0415
        Account,
        query_count,
        TransactionCategory,
        TransactionSplit,
        YIELD_PER,
    )

    s = transactions_query.session
    accounts = Account.map_name(s)
    categories = TransactionCategory.map_name_emoji(s)

    query = transactions_query.with_entities(
        TransactionSplit.date_ord,
        TransactionSplit.account_id,
        TransactionSplit.payee,
        TransactionSplit.memo,
        TransactionSplit.category_id,
        TransactionSplit.tag,
        TransactionSplit.amount,
    ).order_by(TransactionSplit.date_ord)
    n = query_count(query)

    header = [
        "Date",
        "Account",
        "Payee",
        "Memo",
        "Category",
        "Tag",
        "Amount",
    ]
    lines: list[list[str]] = []
    for (
        date,
        acct_id,
        payee,
        memo,
        t_cat_id,
        tag,
        amount,
    ) in tqdm.tqdm(query.yield_per(YIELD_PER), total=n, desc="Exporting"):
        lines.append(
            [
                datetime.date.fromordinal(date).isoformat(),
                accounts[acct_id],
                payee,
                memo,
                categories[t_cat_id],
                tag,
                utils.format_financial(amount),
            ],
        )

    writer = csv.writer(file)
    writer.writerow(header)
    writer.writerows(lines)
