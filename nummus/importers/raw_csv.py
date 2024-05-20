"""Raw CSV importers."""

from __future__ import annotations

import csv
import datetime
import io
import types

from typing_extensions import override

from nummus import utils
from nummus.importers.base import TransactionImporter, TxnDict, TxnDicts


class CSVTransactionImporter(TransactionImporter):
    """Import a CSV of transactions.

    Required Columns: account,date,amount,payee,description

    Other columns are allowed
    """

    _COLUMNS = types.MappingProxyType(
        {
            "account": (True, str),
            "date": (True, datetime.date.fromisoformat),
            "amount": (True, utils.parse_real),
            "payee": (True, str),
            "description": (False, str),
            "category": (False, str),
            "subcategory": (False, str),
            "tag": (False, str),
            "asset": (False, str),
            "asset_quantity": (False, utils.parse_real),
        },
    )

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
        for k, (required, _) in cls._COLUMNS.items():
            if required and k not in header:
                return False
        return True

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
            txn: TxnDict = {}
            for key, (required, cleaner) in self._COLUMNS.items():
                value = row.get(key)
                if value:
                    txn[key] = cleaner(value)
                elif required:
                    msg = f"CSV is missing column: {key}"
                    raise KeyError(msg)
            statement = txn.get("description")
            if statement is None:
                if "asset" in txn:
                    statement = f"Asset transaction {txn['asset']}"
                else:
                    msg = "CSV is missing description for non-asset transaction"
                    raise KeyError(msg)
            txn["statement"] = statement
            transactions.append(txn)
        return transactions
