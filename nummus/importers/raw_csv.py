"""Raw CSV importers."""

from __future__ import annotations

import csv
import datetime
import io
from typing import override, TYPE_CHECKING

from nummus import exceptions as exc
from nummus import utils
from nummus.importers.base import TransactionImporter

if TYPE_CHECKING:
    from nummus.importers.base import TxnDict, TxnDicts


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
            raise exc.WrongImporterBufferError

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
            raise exc.WrongImporterBufferError
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
                "asset": row.get("asset") or None,
                "asset_quantity": utils.parse_real(
                    row.get("asset_quantity"),
                    precision=9,
                ),
            }
            transactions.append(txn)
        return transactions
