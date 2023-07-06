"""Test module nummus.importers.raw_csv
"""

import typing as t

from nummus import importers
from nummus.importers import base

from tests import base as test_base


class Derived(base.TransactionImporter):
  """Test class implementing abstract methods
  """

  @classmethod
  def is_importable(cls, name: str, buf: bytes) -> bool:
    return False

  def run(self) -> t.List[base.TransactionDict]:
    return []


class TestCSVTransactionImporter(test_base.TestBase):
  """Test CSVTransactionImporter class
  """

  def test_init_properties(self):
    self.assertRaises(ValueError, Derived)

    path = self._DATA_ROOT.joinpath("transactions_required.csv")
    with open(path, "rb") as file:
      buf = file.read()

    i = Derived(buf=buf)
    self.assertEqual(buf, i._buf)  # pylint: disable=protected-access

    i = Derived(path=path)
    self.assertEqual(buf, i._buf)  # pylint: disable=protected-access

  def test_get_importer(self):
    files = {
        "transactions_required.csv": importers.CSVTransactionImporter,
        "transactions_extras.csv": importers.CSVTransactionImporter,
        "transactions_lacking.csv": None
    }
    for f, cls in files.items():
      path = self._DATA_ROOT.joinpath(f)
      i = importers.get_importer(path)
      if cls is None:
        self.assertIsNone(i)
      else:
        self.assertIsInstance(i, cls)
