from __future__ import annotations

import datetime
import io

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
        self.assertIn("Import File", result)
        self.assertIn("Upload", result)

        result, _ = self.web_post(endpoint)
        self.assertIn("No file selected", result)

        path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name)},
        )
        self.assertIn("Could not find an importer for file", result)

        path = self._DATA_ROOT.joinpath("transactions_corrupt.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name)},
        )
        self.assertIn("CSVTransactionImporter failed to import file", result)

        path = self._DATA_ROOT.joinpath("transactions_bad_category.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name)},
        )
        self.assertIn("Could not find category 'Not a category'", result)

        file = io.BytesIO(b"Account,Date,Amount,Statement\n")
        result, _ = self.web_post(
            endpoint,
            data={"file": (file, "transactions_empty.csv")},
        )
        self.assertIn(
            "CSVTransactionImporter did not import any transactions for file",
            result,
        )

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name)},
        )
        self.assertIn("File successfully imported", result)

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name)},
        )
        self.assertIn(f"File already imported on {today}", result)
        self.assertIn("Force Import", result)

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        result, _ = self.web_post(
            endpoint,
            data={"file": (path, path.name), "force": True},
        )
        self.assertIn("File successfully imported", result)
