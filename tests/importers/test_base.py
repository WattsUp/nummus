from __future__ import annotations

from nummus import importers
from nummus.importers import base
from tests import base as test_base


class Derived(base.TransactionImporter):
    @classmethod
    def is_importable(cls, name: str, buf: bytes) -> bool:
        _ = name
        _ = buf
        return False

    def run(self) -> base.TxnDicts:
        return []


class TestCSVTransactionImporter(test_base.TestBase):
    def test_init_properties(self) -> None:
        self.assertRaises(ValueError, Derived)

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        with path.open("rb") as file:
            buf = file.read()

        i = Derived(buf=buf)
        self.assertEqual(i._buf, buf)  # noqa: SLF001

        i = Derived(path=path)
        self.assertEqual(i._buf, buf)  # noqa: SLF001

    def test_get_importer(self) -> None:
        files = {
            "transactions_required.csv": importers.CSVTransactionImporter,
            "transactions_extras.csv": importers.CSVTransactionImporter,
            "transactions_lacking.csv": None,
        }
        for f, cls in files.items():
            path = self._DATA_ROOT.joinpath(f)
            i = importers.get_importer(path)
            if cls is None:
                self.assertIsNone(i)
            else:
                self.assertIsInstance(i, cls)
