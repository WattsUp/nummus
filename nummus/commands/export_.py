"""Export transactions to CSV."""

from __future__ import annotations

import csv
import datetime
from typing import TYPE_CHECKING

import tqdm

from nummus import utils
from nummus.models import Account, TransactionCategory, TransactionSplit, YIELD_PER

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import orm

    from nummus import portfolio


def export(
    p: portfolio.Portfolio,
    path: Path,
    start: datetime.date | None,
    end: datetime.date | None,
) -> int:
    """Export transactions to CSV.

    Args:
        p: Working Portfolio
        path: Path to CSV output
        start: Start date to filter transactions
        end: End date to filter transactions

    Returns:
        0 on success
        non-zero on failure
    """
    with p.get_session() as s:
        query = (
            s.query(TransactionSplit)
            .where(
                TransactionSplit.asset_id.is_(None),
            )
            .with_entities(TransactionSplit.amount)
        )
        if start is not None:
            query = query.where(TransactionSplit.date_ord >= start.toordinal())
        if end is not None:
            query = query.where(TransactionSplit.date_ord <= end.toordinal())

        write_csv(path, query)
    return 0


def write_csv(
    path: Path,
    transactions_query: orm.Query[TransactionSplit],
) -> None:
    """Write transactions to CSV file.

    Args:
        path: Path to CSV file
        transactions_query: ORM query to obtain TransactionSplits
    """
    s = transactions_query.session
    accounts = Account.map_name(s)
    categories = TransactionCategory.map_name(s)

    query = transactions_query.with_entities(
        TransactionSplit.date_ord,
        TransactionSplit.account_id,
        TransactionSplit.payee,
        TransactionSplit.description,
        TransactionSplit.category_id,
        TransactionSplit.tag,
        TransactionSplit.amount,
    ).order_by(TransactionSplit.date_ord)
    n = query.count()

    header = [
        "Date",
        "Account",
        "Payee",
        "Description",
        "Category",
        "Tag",
        "Amount",
    ]
    lines: list[list[str]] = []
    for (
        date,
        acct_id,
        payee,
        description,
        t_cat_id,
        tag,
        amount,
    ) in tqdm.tqdm(query.yield_per(YIELD_PER), total=n, desc="Exporting"):
        lines.append([
            datetime.date.fromordinal(date).isoformat(),
            accounts[acct_id],
            payee,
            description,
            categories[t_cat_id],
            tag,
            utils.format_financial(amount),
        ])

    with path.open("w", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(header)
        writer.writerows(lines)
