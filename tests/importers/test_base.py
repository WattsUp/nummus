from __future__ import annotations

from nummus import exceptions as exc
from nummus import importers
from nummus.importers import base
from tests import base as test_base


class Derived(base.TransactionImporter):
    @classmethod
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: list[str] | None,
    ) -> bool:
        _ = suffix
        _ = buf
        _ = buf_pdf
        return False

    def run(self) -> base.TxnDicts:
        return []


class TestCSVTransactionImporter(test_base.TestBase):
    def test_init_properties(self) -> None:
        self.assertRaises(ValueError, Derived)

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        with path.open("rb") as file:
            buf = file.read()
        buf_pdf = buf.decode().splitlines()

        i = Derived(buf=buf)
        self.assertEqual(i._buf, buf)  # noqa: SLF001

        i = Derived(buf_pdf=buf_pdf)
        self.assertEqual(i._buf_pdf, buf_pdf)  # noqa: SLF001

    def test_get_importer(self) -> None:
        path_debug = self._TEST_ROOT.joinpath("portfolio.importer_debug")
        available = importers.get_importers(None)
        files = {
            "transactions_required.csv": importers.CSVTransactionImporter,
            "transactions_extras.csv": importers.CSVTransactionImporter,
            "transactions_lacking.csv": None,
            "banana_bank_statement.pdf": None,
        }
        for f, cls in files.items():
            path = self._DATA_ROOT.joinpath(f)
            if cls is None:
                self.assertRaises(
                    exc.UnknownImporterError,
                    importers.get_importer,
                    path,
                    path_debug,
                    available,
                )
            else:
                i = importers.get_importer(path, path_debug, available)
                self.assertIsInstance(i, cls, f"{f} did not return {cls}")
            self.assertTrue(
                path_debug.exists(),
                "Debug file unexpectedly does not exists",
            )
            path_debug.unlink()

    def test_get_importers(self) -> None:
        target = (importers.CSVTransactionImporter,)
        result = importers.get_importers(None)
        self.assertEqual(result, target)

        path = self._DATA_ROOT
        result = importers.get_importers(path)
        self.assertEqual(result[: len(target)], target)

        r = result[-1]
        self.assertEqual(
            f"{r.__module__}.{r.__name__}",
            "custom_importer.BananaBankImporter",
        )
