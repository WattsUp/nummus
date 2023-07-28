"""Financial source importers
"""

import pathlib

from nummus.importers.base import TransactionImporter, TxnDict, TxnDicts
from nummus.importers.raw_csv import CSVTransactionImporter


def get_importer(path: str) -> TransactionImporter:
  """Get the best importer for a file

  Args:
    path: Path to file

  Returns:
    Initialized Importer
  """
  p = pathlib.Path(path)

  with open(p, "rb") as file:
    buf = file.read()

  available = [CSVTransactionImporter]

  for i in available:
    if i.is_importable(p.name, buf):
      return i(buf=buf)
  return None
