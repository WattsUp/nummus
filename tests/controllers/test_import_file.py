from __future__ import annotations

import datetime
import io
from unittest import mock

from nummus.models import Account, AccountCategory
from tests.controllers.base import WebTestBase


class TestImportFile(WebTestBase):
    def test_import_file(self) -> None:
        p = self._portfolio
        self._setup_portfolio()

        with p.begin_session() as s:
            acct = Account(
                name="Monkey Investments",
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            s.add(acct)

        today = datetime.date.today()

        endpoint = "import_file.import_file"
        result, _ = self.web_get(endpoint)
        self.assertIn("Import file", result)
        self.assertIn("Upload", result)

        result, _ = self.web_post(endpoint)
        self.assertIn("No file selected", result)

        path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result, _ = self.web_post(
                endpoint,
                data={"file": (path, path.name)},
            )
        self.assertIn("Could not find an importer for file", result)
        # stack trace not printed
        self.assertEqual(fake_stderr.getvalue(), "")

        path = self._DATA_ROOT.joinpath("transactions_corrupt.csv")
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result, _ = self.web_post(
                endpoint,
                data={"file": (path, path.name)},
            )
        self.assertIn("CSVTransactionImporter failed to import file", result)
        # stack trace printed
        self.assertNotEqual(fake_stderr.getvalue(), "")

        path = self._DATA_ROOT.joinpath("transactions_future.csv")
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result, _ = self.web_post(
                endpoint,
                data={"file": (path, path.name)},
            )
        self.assertIn("Cannot create transaction in the future", result)
        # stack trace not printed
        self.assertEqual(fake_stderr.getvalue(), "")

        file = io.BytesIO(b"Account,Date,Amount,Statement\n")
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result, _ = self.web_post(
                endpoint,
                data={"file": (file, "transactions_empty.csv")},
            )
        self.assertIn(
            "CSVTransactionImporter did not import any transactions for file",
            result,
        )
        # stack trace printed
        self.assertNotEqual(fake_stderr.getvalue(), "")

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name)},
        )
        self.assertIn("File successfully imported", result)

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            result, _ = self.web_post(
                endpoint,
                data={"file": (path, path.name)},
            )
        self.assertIn(f"File already imported on {today}", result)
        self.assertIn("Force Import", result)
        # stack trace not printed
        self.assertEqual(fake_stderr.getvalue(), "")

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name), "force": True},
        )
        self.assertIn("File successfully imported", result)
