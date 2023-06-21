"""Test module nummus.importers.raw_csv
"""

import datetime

from nummus import models
from nummus.importers import raw_csv

from tests import base


class TestCSVTransactionImporter(base.TestBase):
  """Test CSVTransactionImporter class
  """

  def test_is_importable(self):
    path = "Not a CSV"
    result = raw_csv.CSVTransactionImporter.is_importable(path, None)
    self.assertFalse(result)

    path = self._DATA_ROOT.joinpath("transactions_required.csv")
    with open(path, "rb") as file:
      buf = file.read()
    result = raw_csv.CSVTransactionImporter.is_importable(path.name, buf)
    self.assertTrue(result)

    path = self._DATA_ROOT.joinpath("transactions_extras.csv")
    with open(path, "rb") as file:
      buf = file.read()
    result = raw_csv.CSVTransactionImporter.is_importable(path.name, buf)
    self.assertTrue(result)

    path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
    with open(path, "rb") as file:
      buf = file.read()
    result = raw_csv.CSVTransactionImporter.is_importable(path.name, buf)
    self.assertFalse(result)

  def test_run(self):
    path = self._DATA_ROOT.joinpath("transactions_lacking.csv")
    i = raw_csv.CSVTransactionImporter(path=path)
    self.assertRaises(KeyError, i.run)

    path = self._DATA_ROOT.joinpath("transactions_required.csv")
    i = raw_csv.CSVTransactionImporter(path=path)
    target = [{
        "account": "Monkey Bank",
        "date": datetime.date(2023, 1, 1),
        "total": 1000.0,
        "payee": "Employer",
        "description": "Paycheck"
    }, {
        "account": "Monkey Bank",
        "date": datetime.date(2023, 1, 2),
        "total": -12.34,
        "payee": "Monkey Store",
        "description": "Banana"
    }, {
        "account": "Monkey Bank",
        "date": datetime.date(2023, 1, 2),
        "total": -900.0,
        "payee": "Monkey Investments",
        "description": "Account Transfer"
    }, {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "total": 900.0,
        "payee": "Monkey Investments",
        "description": "Account Transfer"
    }]
    result = i.run()
    self.assertEqual(len(target), len(result))
    for t, r in zip(target, result):
      for k, t_v in t.items():
        r_v = r.pop(k)
        self.assertEqual(t_v, r_v)
      # No remaining items
      self.assertEqual(0, len(r))

    path = self._DATA_ROOT.joinpath("transactions_extras.csv")
    i = raw_csv.CSVTransactionImporter(path=path)
    target = [{
        "account": "Monkey Bank",
        "date": datetime.date(2023, 1, 1),
        "total": 1000.0,
        "payee": "Employer",
        "description": "Paycheck",
        "category": models.TransactionCategory.INCOME,
        "subcategory": "Paychecks"
    }, {
        "account": "Monkey Bank",
        "date": datetime.date(2023, 1, 2),
        "total": -12.34,
        "payee": "Monkey Store",
        "description": "Banana",
        "category": models.TransactionCategory.FOOD,
        "subcategory": "Groceries",
        "tag": "Fruit",
        "sales_tax": -1.23
    }, {
        "account": "Monkey Bank",
        "date": datetime.date(2023, 1, 2),
        "total": -900.0,
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "category": models.TransactionCategory.TRANSFER
    }, {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 2),
        "total": 900.0,
        "payee": "Monkey Investments",
        "description": "Account Transfer",
        "category": models.TransactionCategory.TRANSFER
    }, {
        "account": "Monkey Investments",
        "date": datetime.date(2023, 1, 3),
        "total": -900.0,
        "payee": "Monkey Investments",
        "description": "Security Exchange",
        "category": models.TransactionCategory.INSTRUMENT,
        "asset": "BANANA",
        "asset_quantity": 32.1234
    }]
    result = i.run()
    self.assertEqual(len(target), len(result))
    for t, r in zip(target, result):
      for k, t_v in t.items():
        r_v = r.pop(k)
        self.assertEqual(t_v, r_v)
      # No remaining items
      self.assertEqual(0, len(r), msg=f"Extra keys: {list(r.keys())}")
