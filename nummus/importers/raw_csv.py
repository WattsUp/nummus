"""Raw CSV importers
"""

import typing as t

import csv
import datetime
import io

from nummus import common, models
from nummus.importers import base


class CSVTransactionImporter(base.TransactionImporter):
  """Import a CSV of transactions

  Required Columns: account,date,total,payee,description

  Other columns are allowed
  """

  _COLUMNS: t.Dict[str, t.Tuple[bool, t.Callable[[str], object]]] = {
      "account": (True, str),
      "date": (True, datetime.date.fromisoformat),
      "total": (True, common.parse_financial),
      "payee": (True, str),
      "description": (True, str),
      "sales_tax": (False, common.parse_financial),
      "category": (False, models.TransactionCategory.parse),
      "subcategory": (False, str),
      "tag": (False, str),
      "asset": (False, str),
      "asset_quantity": (False, common.parse_financial)
  }

  @classmethod
  def is_importable(cls, name: str, buf: bytes) -> bool:
    if not name.endswith(".csv"):
      return False

    # Check if the columns start with the expected ones
    first_line = buf.split(b"\n", 1)[0].decode().lower().replace(" ", "_")
    header = list(csv.reader(io.StringIO(first_line)))[0]
    for k, item in cls._COLUMNS.items():
      required, _ = item
      if required and k not in header:
        return False
    return True

  def run(self) -> t.List[base.TransactionDict]:
    first_line, remaining = self._buf.decode().split("\n", 1)
    first_line = first_line.lower().replace(" ", "_")
    reader = csv.DictReader(io.StringIO(first_line + "\n" + remaining))
    transactions: t.List[base.TransactionDict] = []
    for row in reader:
      txn: base.TransactionDict = {}
      for key, item in self._COLUMNS.items():
        required, cleaner = item
        value = row.get(key)
        if value in [None, ""]:
          if required:
            raise KeyError(f"CSV is missing column: {key}")
        else:
          txn[key] = cleaner(value)
      txn["statement"] = txn["description"]
      transactions.append(txn)
    return transactions
