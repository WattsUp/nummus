"""Test module nummus.importers.raw_csv
"""

import datetime
import decimal

from nummus import models
from nummus.importers import raw_csv

from tests import base

# Other unit tests use the file transactions_extras.csv
TRANSACTIONS_EXTRAS = [{
    "account": "Monkey Bank Checking",
    "date": datetime.date(2023, 1, 1),
    "total": decimal.Decimal("1000.0"),
    "payee": "Employer",
    "description": "Paycheck",
    "statement": "Paycheck",
    "category": models.TransactionCategory.INCOME,
    "subcategory": "Paychecks"
}, {
    "account": "Monkey Bank Checking",
    "date": datetime.date(2023, 1, 2),
    "total": decimal.Decimal("-12.34"),
    "payee": "Monkey Store",
    "description": "Banana",
    "statement": "Banana",
    "category": models.TransactionCategory.FOOD,
    "subcategory": "Groceries",
    "tag": "Fruit",
    "sales_tax": decimal.Decimal("-1.23")
}, {
    "account": "Monkey Bank Checking",
    "date": datetime.date(2023, 1, 2),
    "total": decimal.Decimal("-900.0"),
    "payee": "Monkey Investments",
    "description": "Account Transfer",
    "statement": "Account Transfer",
    "category": models.TransactionCategory.TRANSFER
}, {
    "account": "Monkey Investments",
    "date": datetime.date(2023, 1, 2),
    "total": decimal.Decimal("900.0"),
    "payee": "Monkey Investments",
    "description": "Account Transfer",
    "statement": "Account Transfer",
    "category": models.TransactionCategory.TRANSFER
}, {
    "account": "Monkey Investments",
    "date": datetime.date(2023, 1, 3),
    "total": decimal.Decimal("-900.0"),
    "payee": "Monkey Investments",
    "description": "Security Exchange",
    "statement": "Security Exchange",
    "category": models.TransactionCategory.INSTRUMENT,
    "asset": "BANANA",
    "asset_quantity": decimal.Decimal("32.1234")
}, {
    "account": "Monkey Investments",
    "date": datetime.date(2023, 2, 1),
    "total": decimal.Decimal("1234.56"),
    "payee": "Monkey Investments",
    "description": "Profit Maker",
    "statement": "Profit Maker",
    "category": models.TransactionCategory.INSTRUMENT,
    "asset": "BANANA",
    "asset_quantity": decimal.Decimal("-32.1234")
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
        "total": decimal.Decimal("1000.0"),
        "payee": "Employer",
        "description": "Paycheck",
        "statement": "Paycheck"
    }, {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "total": decimal.Decimal("-12.34"),
        "payee": "Monkey Store",
        "description": "Banana",
        "statement": "Banana"
    }, {
        "account": "Monkey Bank Checking",
        "date": datetime.date(2023, 1, 2),
        "total": decimal.Decimal("-900.0"),
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "statement": "Account Transfer"
    }, {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "total": decimal.Decimal("900.0"),
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
