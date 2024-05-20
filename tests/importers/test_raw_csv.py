from __future__ import annotations

import datetime
from decimal import Decimal

from nummus.importers import raw_csv
from tests import base

# Other unit tests use the file transactions_extras.csv
TRANSACTIONS_EXTRAS = [
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 1),
        "amount": Decimal("1000.0"),
        "payee": "Employer",
        "description": "Paycheck",
        "statement": "Paycheck",
        "category": "Paychecks/Salary",
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-12.34"),
        "payee": "Monkey Store",
        "description": "Banana",
        "statement": "Banana",
        "category": "Groceries",
        "tag": "Fruit",
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-900.0"),
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "statement": "Account Transfer",
        "category": "Transfers",
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("900.0"),
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "statement": "Account Transfer",
        "category": "Transfers",
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 3),
        "amount": Decimal("-900.0"),
        "payee": "Monkey Investments",
        "statement": "Asset transaction BANANA",
        "category": "Securities Traded",
        "asset": "BANANA",
        "asset_quantity": Decimal("32.1234"),
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 2, 1),
        "amount": Decimal("1234.56"),
        "payee": "Monkey Investments",
        "description": "Profit Maker",
        "statement": "Profit Maker",
        "category": "Securities Traded",
        "asset": "BANANA",
        "asset_quantity": Decimal("-32.1234"),
    },
]


class TestCSVTransactionImporter(base.TestBase):
    def test_is_importable(self) -> None:
        self.assertRaises(
            ValueError,
            raw_csv.CSVTransactionImporter.is_importable,
            ".csv",
            None,
            None,
        )

        result = raw_csv.CSVTransactionImporter.is_importable("", b"", None)
        self.assertFalse(result, "File is unexpectedly importable")

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        with path.open("rb") as file:
            buf = file.read()
        result = raw_csv.CSVTransactionImporter.is_importable(path.suffix, buf, None)
        self.assertTrue(result, "File is unexpectedly un-importable")

        path = self._DATA_ROOT.joinpath("transactions_extras.csv")
        with path.open("rb") as file:
            buf = file.read()
        result = raw_csv.CSVTransactionImporter.is_importable(path.suffix, buf, None)
        self.assertTrue(result, "File is unexpectedly un-importable")

        path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
        with path.open("rb") as file:
            buf = file.read()
        result = raw_csv.CSVTransactionImporter.is_importable(path.suffix, buf, None)
        self.assertFalse(result, "File is unexpectedly importable")

    def test_run(self) -> None:
        i = raw_csv.CSVTransactionImporter(None, [""])
        self.assertRaises(ValueError, i.run)

        path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
        with path.open("rb") as file:
            buf = file.read()
        i = raw_csv.CSVTransactionImporter(buf=buf)
        self.assertRaises(KeyError, i.run)

        path = self._DATA_ROOT.joinpath("transactions_lacking_desc.csv")
        with path.open("rb") as file:
            buf = file.read()
        i = raw_csv.CSVTransactionImporter(buf=buf)
        self.assertRaises(KeyError, i.run)

        path = self._DATA_ROOT.joinpath("transactions_required.csv")
        with path.open("rb") as file:
            buf = file.read()
        i = raw_csv.CSVTransactionImporter(buf=buf)
        target = [
            {
                "account": "Monkey Bank Checking",
                "date": datetime.date(2023, 1, 1),
                "amount": Decimal("1000.0"),
                "payee": "Employer",
                "description": "Paycheck",
                "statement": "Paycheck",
            },
            {
                "account": "Monkey Bank Checking",
                "date": datetime.date(2023, 1, 2),
                "amount": Decimal("-12.34"),
                "payee": "Monkey Store",
                "description": "Banana",
                "statement": "Banana",
            },
            {
                "account": "Monkey Bank Checking",
                "date": datetime.date(2023, 1, 2),
                "amount": Decimal("-900.0"),
                "payee": "Monkey Investments",
                "description": "Account Transfer",
                "statement": "Account Transfer",
            },
            {
                "account": "Monkey Investments",
                "date": datetime.date(2023, 1, 2),
                "amount": Decimal("900.0"),
                "payee": "Monkey Investments",
                "description": "Account Transfer",
                "statement": "Account Transfer",
            },
        ]
        result = i.run()
        self.assertEqual(len(result), len(target))
        for tgt, res in zip(target, result, strict=True):
            for k, t_v in tgt.items():
                r_v = res.pop(k)
                self.assertEqual(r_v, t_v)
            # No remaining items
            self.assertEqual(len(res), 0)

        path = self._DATA_ROOT.joinpath("transactions_extras.csv")
        with path.open("rb") as file:
            buf = file.read()
        i = raw_csv.CSVTransactionImporter(buf=buf)
        target = TRANSACTIONS_EXTRAS

        result = i.run()
        self.assertEqual(len(result), len(target))
        for tgt, res in zip(target, result, strict=True):
            for k, t_v in tgt.items():
                r_v = res.pop(k)
                self.assertEqual(r_v, t_v)
            # No remaining items
            self.assertEqual(len(res), 0, msg=f"Extra keys: {list(res.keys())}")
