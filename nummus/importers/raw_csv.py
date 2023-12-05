"""Raw CSV importers."""

from __future__ import annotations

import csv
import datetime
import io
import types
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus import utils
from nummus.importers.base import TransactionImporter, TxnDict, TxnDicts

if TYPE_CHECKING:
    from pathlib import Path


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
            "description": (True, str),
            "sales_tax": (False, utils.parse_real),
            "category": (False, str),
            "subcategory": (False, str),
            "tag": (False, str),
            "asset": (False, str),
            "asset_quantity": (False, utils.parse_real),
        },
    )

    @classmethod
    @override
    def is_importable(cls, name: Path, buf: bytes) -> bool:
        if name.suffix != ".csv":
            return False

        # Check if the columns start with the expected ones
        first_line = buf.split(b"\n", 1)[0].decode().lower().replace(" ", "_")
        header = next(csv.reader(io.StringIO(first_line)))
        for k, item in cls._COLUMNS.items():
            required, _ = item
            if required and k not in header:
                return False
        return True

    @override
    def run(self) -> TxnDicts:
        first_line, remaining = self._buf.decode().split("\n", 1)
        first_line = first_line.lower().replace(" ", "_")
        reader = csv.DictReader(io.StringIO(first_line + "\n" + remaining))
        transactions: TxnDicts = []
        for row in reader:
            txn: TxnDict = {}
            for key, item in self._COLUMNS.items():
                required, cleaner = item
                value = row.get(key)
                if value:
                    txn[key] = cleaner(value)
                elif required:
                    msg = f"CSV is missing column: {key}"
                    raise KeyError(msg)
            txn["statement"] = txn["description"]
            transactions.append(txn)
        return transactions
