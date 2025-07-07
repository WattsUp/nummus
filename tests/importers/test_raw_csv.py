from __future__ import annotations

import datetime
from decimal import Decimal

import pytest

from nummus.importers import raw_csv

# Other unit tests use the files, share target
TRANSACTIONS_REQUIRED = [
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 1),
        "amount": Decimal("1000.0"),
        "statement": "Paycheck",
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-12.34"),
        "statement": "Banana",
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-900.0"),
        "statement": "Account Transfer",
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("900.0"),
        "statement": "Account Transfer",
    },
]

TRANSACTIONS_EXTRAS: raw_csv.TxnDicts = [
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 1),
        "amount": Decimal("1000.0"),
        "statement": "Paycheck",
        "payee": "Employer",
        "memo": "Paycheck",
        "category": "Paychecks/Salary",
        "tag": None,
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-12.34"),
        "statement": "Banana",
        "payee": "Monkey Store",
        "memo": "Banana",
        "category": "Groceries",
        "tag": "Fruit",
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("-900.0"),
        "statement": "Account Transfer",
        "payee": "Monkey Investments",
        "memo": "Account Transfer",
        "category": "Transfers",
        "tag": None,
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "amount": Decimal("900.0"),
        "statement": "Account Transfer",
        "payee": "Monkey Investments",
        "memo": "Account Transfer",
        "category": "Transfers",
        "tag": None,
        "asset": None,
        "asset_quantity": None,
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 3),
        "amount": Decimal("-900.0"),
        "statement": "",
        "payee": "Monkey Investments",
        "memo": None,
        "category": "Securities Traded",
        "tag": None,
        "asset": "BANANA",
        "asset_quantity": Decimal("32.1234"),
    },
    {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 2, 1),
        "amount": Decimal("1234.56"),
        "statement": "Profit Maker",
        "payee": "Monkey Investments",
        "memo": "Profit Maker",
        "category": "Securities Traded",
        "tag": None,
        "asset": "BANANA",
        "asset_quantity": Decimal("-32.1234"),
    },
]


@pytest.mark.xfail
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


@pytest.mark.xfail
def test_run(self) -> None:
    i = raw_csv.CSVTransactionImporter(None, [""])
    self.assertRaises(ValueError, i.run)

    path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
    with path.open("rb") as file:
        buf = file.read()
    i = raw_csv.CSVTransactionImporter(buf=buf)
    self.assertRaises(KeyError, i.run)

    path = self._DATA_ROOT.joinpath("transactions_required.csv")
    with path.open("rb") as file:
        buf = file.read()
    i = raw_csv.CSVTransactionImporter(buf=buf)
    target = TRANSACTIONS_REQUIRED
    result = i.run()
    assert len(result) == len(target)
    for tgt, res in zip(target, result, strict=True):
        res_d = dict(res)  # Convert type so items can be popped
        for k, t_v in tgt.items():
            r_v = res_d.pop(k)
            assert r_v == t_v, f"{k} unexpectedly differs"
        self.assertTrue(
            all(item is None for item in res_d.values()),
            f"Not all remaining items are None: {res_d}",
        )

    path = self._DATA_ROOT.joinpath("transactions_extras.csv")
    with path.open("rb") as file:
        buf = file.read()
    i = raw_csv.CSVTransactionImporter(buf=buf)
    target = TRANSACTIONS_EXTRAS
    result = i.run()
    assert len(result) == len(target)
    for tgt, res in zip(target, result, strict=True):
        res_d = dict(res)  # Convert type so items can be popped
        for k, t_v in tgt.items():
            r_v = res_d.pop(k)
            assert r_v == t_v, f"{k} unexpectedly differs"
        self.assertEqual(
            len(res_d),
            0,
            f"Not all fields are covered by TRANSACTIONS_EXTRAS: {res}",
        )

    buf = (
        b"Account,Date,Amount,Statement\n" b"Monkey Bank Checking,2023-01-01,,Paycheck"
    )
    i = raw_csv.CSVTransactionImporter(buf=buf)
    self.assertRaises(ValueError, i.run)
