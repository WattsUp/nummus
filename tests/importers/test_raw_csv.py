"""Test module nummus.importers.raw_csv
"""

import datetime
from decimal import Decimal

from nummus.importers import raw_csv

from tests import base

# Other unit tests use the file transactions_extras.csv
TRANSACTIONS_EXTRAS = [{
    "account": "Monkey Bank Checking",
    "date": datetime.date(2023, 1, 1),
    "total": Decimal("1000.0"),
    "payee": "Employer",
    "description": "Paycheck",
    "statement": "Paycheck",
    "category": "Paychecks/Salary"
}, {
    "account": "Monkey Bank Checking",
    "date": datetime.date(2023, 1, 2),
    "total": Decimal("-12.34"),
    "payee": "Monkey Store",
    "description": "Banana",
    "statement": "Banana",
    "category": "Groceries",
    "tag": "Fruit"
}, {
    "account": "Monkey Bank Checking",
    "date": datetime.date(2023, 1, 2),
    "total": Decimal("-900.0"),
    "payee": "Monkey Investments",
    "description": "Account Transfer",
    "statement": "Account Transfer",
    "category": "Transfers"
}, {
    "account": "Monkey Investments",
    "date": datetime.date(2023, 1, 2),
    "total": Decimal("900.0"),
    "payee": "Monkey Investments",
    "description": "Account Transfer",
    "statement": "Account Transfer",
    "category": "Transfers"
}, {
    "account": "Monkey Investments",
    "date": datetime.date(2023, 1, 3),
    "total": Decimal("-900.0"),
    "payee": "Monkey Investments",
    "description": "Security Exchange",
    "statement": "Security Exchange",
    "category": "Securities Traded",
    "asset": "BANANA",
    "asset_quantity": Decimal("32.1234")
}, {
    "account": "Monkey Investments",
    "date": datetime.date(2023, 2, 1),
    "total": Decimal("1234.56"),
    "payee": "Monkey Investments",
    "description": "Profit Maker",
    "statement": "Profit Maker",
    "category": "Securities Traded",
    "asset": "BANANA",
    "asset_quantity": Decimal("-32.1234")
}]


class TestCSVTransactionImporter(base.TestBase):
  """Test CSVTransactionImporter class
  """

  def test_is_importable(self):
    path = "Not a CSV"
    result = raw_csv.CSVTransactionImporter.is_importable(path, None)
    self.assertFalse(result, "File is unexpectedly importable")

    path = self._DATA_ROOT.joinpath("transactions_required.csv")
    with open(path, "rb") as file:
      buf = file.read()
    result = raw_csv.CSVTransactionImporter.is_importable(path.name, buf)
    self.assertTrue(result, "File is unexpectedly un-importable")

    path = self._DATA_ROOT.joinpath("transactions_extras.csv")
    with open(path, "rb") as file:
      buf = file.read()
    result = raw_csv.CSVTransactionImporter.is_importable(path.name, buf)
    self.assertTrue(result, "File is unexpectedly un-importable")

    path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
    with open(path, "rb") as file:
      buf = file.read()
    result = raw_csv.CSVTransactionImporter.is_importable(path.name, buf)
    self.assertFalse(result, "File is unexpectedly importable")

  def test_run(self):
    path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
    i = raw_csv.CSVTransactionImporter(path=path)
    self.assertRaises(KeyError, i.run)

    path = self._DATA_ROOT.joinpath("transactions_required.csv")
    i = raw_csv.CSVTransactionImporter(path=path)
    target = [{
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 1),
        "total": Decimal("1000.0"),
        "payee": "Employer",
        "description": "Paycheck",
        "statement": "Paycheck"
    }, {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "total": Decimal("-12.34"),
        "payee": "Monkey Store",
        "description": "Banana",
        "statement": "Banana"
    }, {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "total": Decimal("-900.0"),
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "statement": "Account Transfer"
    }, {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "total": Decimal("900.0"),
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "statement": "Account Transfer"
    }]
    result = i.run()
    self.assertEqual(len(target), len(result))
    for tgt, res in zip(target, result):
      for k, t_v in tgt.items():
        r_v = res.pop(k)
        self.assertEqual(t_v, r_v)
      # No remaining items
      self.assertEqual(0, len(res))

    path = self._DATA_ROOT.joinpath("transactions_extras.csv")
    i = raw_csv.CSVTransactionImporter(path=path)
    target = TRANSACTIONS_EXTRAS

    result = i.run()
    self.assertEqual(len(target), len(result))
    for tgt, res in zip(target, result):
      for k, t_v in tgt.items():
        r_v = res.pop(k)
        self.assertEqual(t_v, r_v)
      # No remaining items
      self.assertEqual(0, len(res), msg=f"Extra keys: {list(res.keys())}")
