"""Raw CSV importers."""

from __future__ import annotations

import csv
import datetime
import io

from typing_extensions import override

from nummus import utils
from nummus.importers.base import TransactionImporter, TxnDict, TxnDicts


class CSVTransactionImporter(TransactionImporter):
    """Import a CSV of transactions.

    Required Columns: account,date,amount,payee,statement

    Other columns are allowed
    """

    @classmethod
    @override
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: list[str] | None,
    ) -> bool:
        if suffix != ".csv":
            return False
        if buf is None or buf_pdf is not None:
            msg = "buf not given with non-pdf suffix"
            raise ValueError(msg)

        # Check if the columns start with the expected ones
        first_line = buf.split(b"\n", 1)[0].decode().lower().replace(" ", "_")
        header = next(csv.reader(io.StringIO(first_line)))
        required = {
            "account",
            "amount",
            "date",
            "statement",
        }
        return required.issubset(header)

    @override
    def run(self) -> TxnDicts:
        if self._buf is None:
            msg = "Importer did not initialized with byte buffer"
            raise ValueError(msg)
        first_line, remaining = self._buf.decode().split("\n", 1)
        first_line = first_line.lower().replace(" ", "_")
        reader = csv.DictReader(io.StringIO(first_line + "\n" + remaining))
        transactions: TxnDicts = []
        for row in reader:
            row: dict[str, str]

            amount = utils.parse_real(row["amount"])
            if amount is None:
                msg = f"Amount column did not import a number: {row}"
                raise ValueError(msg)

            txn: TxnDict = {
                "account": row["account"],
                "date": datetime.date.fromisoformat(row["date"]),
                "amount": amount,
                "statement": row["statement"],
                "payee": row.get("payee") or None,
                "memo": row.get("memo") or None,
                "category": row.get("category") or None,
                "tag": row.get("tag") or None,
                "asset": row.get("asset") or None,
                "asset_quantity": utils.parse_real(
                    row.get("asset_quantity"),
                    precision=9,
                ),
            }
            transactions.append(txn)
        return transactions
