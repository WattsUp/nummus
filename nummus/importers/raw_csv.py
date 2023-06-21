"""Raw CSV importers
"""

from typing import Callable, Dict, List, Tuple, Union

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

  _COLUMNS: Dict[str, Tuple[bool, Callable[[str], object]]] = {
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

  def __init__(self, path: str = None, buf: bytes = None) -> None:
    """Initialize CSV Transaction Importer
    
    Args:
      Provide one or the other
      path: Path to CSV
      buf: Contents of CSV file
    """
    super().__init__()

    if buf is not None:
      self._buf = buf.decode()
    elif path is not None:
      with open(path, "r", encoding="utf-8") as file:
        self._buf = file.read()
    else:
      raise ValueError("Must provide path or buffer")

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

  def run(self) -> List[Dict[str, Union[str, float, datetime.date, object]]]:
    first_line, remaining = self._buf.split("\n", 1)
    first_line = first_line.lower().replace(" ", "_")
    reader = csv.DictReader(io.StringIO(first_line + "\n" + remaining))
    transactions: List[Dict[str, Union[str, float, datetime.date, object]]] = []
    for row in reader:
      t: Dict[str, Union[str, float, datetime.date, object]] = {}
      for key, item in self._COLUMNS.items():
        required, cleaner = item
        value = row.get(key)
        if value in [None, ""]:
          if required:
            raise KeyError(f"CSV is missing column: {key}")
        else:
          t[key] = cleaner(value)
      transactions.append(t)
    return transactions
