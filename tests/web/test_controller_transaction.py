"""Test module nummus.web.controller_transaction
"""

import datetime
import io
import json
from unittest import mock
import warnings

from nummus import portfolio
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           NummusJSONEncoder, Transaction, TransactionCategory,
                           TransactionSplit)

from tests.base import TestBase


class TestControllerTransaction(TestBase):
  """Test controller_transaction methods
  """

  def test_create(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    asset_bananas = Asset(name="bananas", category=AssetCategory.ITEM)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add_all((a, asset_bananas))
      s.commit()
      a_uuid = a.uuid
      asset_bananas_uuid = asset_bananas.uuid

    # Make the minimum
    total = float(self._RNG.uniform(-10, 10))
    statement = self.random_string()
    req = {
        "account_uuid": a_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True,
        "splits": [{
            "total": total
        }]
    }

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.post("/api/transaction", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    with p.get_session() as s:
      t = s.query(Transaction).first()

      self.assertEqual(a, t.account)
      self.assertEqual(today, t.date)
      self.assertEqualWithinError(total, t.total, 1e-6)
      self.assertEqual(statement, t.statement)
      self.assertTrue(t.locked, "Transaction is not locked")
      self.assertEqual(1, len(t.splits))
      t_split = t.splits[0]
      self.assertEqualWithinError(total, t_split.total, 1e-6)

      # Serialize then deserialize
      target = json.loads(json.dumps(t, cls=NummusJSONEncoder))

      s.delete(t_split)
      s.delete(t)
      s.commit()

    result = response.json
    self.assertDictEqual(target, result)

    # Make the maximum
    total = float(self._RNG.uniform(-10, 10))
    sales_tax = float(self._RNG.uniform(-10, 0))
    statement = self.random_string()
    payee = self.random_string()
    description = self.random_string()
    category = self._RNG.choice(TransactionCategory)
    subcategory = self.random_string()
    tag = self.random_string()
    asset_qty = float(self._RNG.uniform(-1, 1))
    req = {
        "account_uuid":
            a_uuid,
        "date":
            today.isoformat(),
        "total":
            total,
        "statement":
            statement,
        "locked":
            True,
        "splits": [{
            "total": total,
            "sales_tax": sales_tax,
            "payee": payee,
            "description": description,
            "category": category.name.lower(),
            "subcategory": subcategory,
            "tag": tag,
            "asset_uuid": asset_bananas_uuid,
            "asset_quantity": asset_qty
        }]
    }

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.post("/api/transaction", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    with p.get_session() as s:
      t = s.query(Transaction).first()

      self.assertEqual(a, t.account)
      self.assertEqual(today, t.date)
      self.assertEqualWithinError(total, t.total, 1e-6)
      self.assertEqual(statement, t.statement)
      self.assertTrue(t.locked, "Transaction is not locked")
      self.assertEqual(1, len(t.splits))
      t_split = t.splits[0]
      self.assertEqualWithinError(total, t_split.total, 1e-6)
      self.assertEqualWithinError(sales_tax, t_split.sales_tax, 1e-6)
      self.assertEqual(payee, t_split.payee)
      self.assertEqual(description, t_split.description)
      self.assertEqual(category, t_split.category)
      self.assertEqual(subcategory, t_split.subcategory)
      self.assertEqual(tag, t_split.tag)
      self.assertEqual(asset_bananas, t_split.asset)
      self.assertEqual(asset_qty, t_split.asset_quantity)

      # Serialize then deserialize
      target = json.loads(json.dumps(t, cls=NummusJSONEncoder))

    result = response.json
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {
        "account_uuid": a_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True
    }
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.post("/api/transaction", json=req)
    self.assertEqual(400, response.status_code)

    # Need at least one split
    req = {
        "account_uuid": a_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True,
        "splits": []
    }
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.post("/api/transaction", json=req)
    self.assertEqual(400, response.status_code)

  def test_get(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts and transactions
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      t = Transaction(account_id=a.id,
                      date=today,
                      total=100,
                      statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=t)
      s.add_all((t, t_split))
      s.commit()
      t_uuid = t.uuid
      target = json.loads(json.dumps(t, cls=NummusJSONEncoder))

    # Get by uuid
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get(f"/api/transaction/{t_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

  def test_update(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts and transactions
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    asset_bananas = Asset(name="bananas", category=AssetCategory.ITEM)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add_all((a, asset_bananas))
      s.commit()
      asset_bananas_uuid = asset_bananas.uuid

      t = Transaction(account_id=a.id,
                      date=today,
                      total=100,
                      statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=t)
      s.add_all((t, t_split))
      s.commit()
      t_uuid = t.uuid
      target = json.loads(json.dumps(t, cls=NummusJSONEncoder))

    # Update
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = self._RNG.choice(TransactionCategory)
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    target["splits"][0]["category"] = new_category_0.name.lower()
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req.pop("uuid")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req["splits"] = [req_split_0]
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.put(f"/api/transaction/{t_uuid}", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    with p.get_session() as s:
      t = s.query(Transaction).where(Transaction.uuid == t_uuid).first()
      self.assertEqual(new_statement, t.statement)
      self.assertEqual(new_date, t.date)
      self.assertEqual(1, len(t.splits))
      t_split = t.splits[0]
      self.assertEqual(new_category_0, t_split.category)

      # Check no other splits were created
      n_splits = s.query(TransactionSplit).count()
      self.assertEqual(1, n_splits)
    result = response.json
    self.assertEqual(target, result)

    # Update and add a split
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = self._RNG.choice(TransactionCategory)
    new_category_1 = self._RNG.choice(TransactionCategory)
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    # Duplicate split
    target["splits"].append(dict(target["splits"][0]))
    target["splits"][0]["category"] = new_category_0.name.lower()
    target["splits"][1]["category"] = new_category_1.name.lower()
    target["splits"][1]["asset_uuid"] = asset_bananas_uuid
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req_split_1 = dict(target["splits"][1])
    req.pop("uuid")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req_split_1.pop("uuid")
    req_split_1.pop("parent_uuid")
    req["splits"] = [req_split_0, req_split_1]
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.put(f"/api/transaction/{t_uuid}", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    with p.get_session() as s:
      t = s.query(Transaction).where(Transaction.uuid == t_uuid).first()
      self.assertEqual(new_statement, t.statement)
      self.assertEqual(new_date, t.date)
      self.assertEqual(2, len(t.splits))
      t_split = t.splits[0]
      self.assertEqual(new_category_0, t_split.category)
      t_split = t.splits[1]
      self.assertEqual(new_category_1, t_split.category)
      self.assertEqual(asset_bananas_uuid, t_split.asset_uuid)

      # Update target t_split_1 uuid since it is new
      target["splits"][1]["uuid"] = t_split.uuid

      # Check first split was reused
      n_splits = s.query(TransactionSplit).count()
      self.assertEqual(2, n_splits)
    result = response.json
    self.assertEqual(target, result)

    # Update and remove a split
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = self._RNG.choice(TransactionCategory)
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    # Keep only the second one
    target["splits"] = [target["splits"][1]]
    target["splits"][0]["category"] = new_category_0.name.lower()
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req.pop("uuid")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req["splits"] = [req_split_0]
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.put(f"/api/transaction/{t_uuid}", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    with p.get_session() as s:
      t = s.query(Transaction).where(Transaction.uuid == t_uuid).first()
      self.assertEqual(new_statement, t.statement)
      self.assertEqual(new_date, t.date)
      self.assertEqual(1, len(t.splits))
      t_split = t.splits[0]
      self.assertEqual(new_category_0, t_split.category)

      # Update target t_split_0 uuid since it might be different
      target["splits"][0]["uuid"] = t_split.uuid

      # Check other split was deleted
      n_splits = s.query(TransactionSplit).count()
      self.assertEqual(1, n_splits)
    result = response.json
    self.assertEqual(target, result)

    # Try to remove all splits
    req["splits"] = []
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.put(f"/api/transaction/{t_uuid}", json=req)
    self.assertEqual(400, response.status_code)

    # Read only properties
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.put(f"/api/transaction/{t_uuid}", json=target)
    self.assertEqual(400, response.status_code)

  def test_delete(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts and transactions
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      t = Transaction(account_id=a.id,
                      date=today,
                      total=100,
                      statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=t)
      s.add_all((t, t_split))
      s.commit()
      t_uuid = t.uuid
      target = json.loads(json.dumps(t, cls=NummusJSONEncoder))

    with p.get_session() as s:
      result = s.query(Transaction).count()
      self.assertEqual(1, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(1, result)

    # Delete by uuid
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.delete(f"/api/transaction/{t_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

    with p.get_session() as s:
      result = s.query(Transaction).count()
      self.assertEqual(0, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    #   # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      for i, category in enumerate(TransactionCategory):
        t = Transaction(account_id=a.id,
                        date=today,
                        total=100,
                        statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=t, category=category)
        s.add_all((t, t_split))
        if i == 0:
          t_split = TransactionSplit(total=10,
                                     parent=t,
                                     category=TransactionCategory.TRAVEL)
          s.add(t_split)
          t_split = TransactionSplit(total=10,
                                     parent=t,
                                     category=TransactionCategory.TRAVEL)
          s.add(t_split)
      s.commit()

    # Get all
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/transactions")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Transaction)
      transactions = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    target = {"transactions": transactions}
    self.assertEqual(target, result)

    # Get only travel
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/transactions?category=travel")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      all_transactions = s.query(Transaction).all()
      transactions = []
      for t in all_transactions:
        if any(t_split.category == TransactionCategory.TRAVEL
               for t_split in t.splits):
          transactions.append(json.loads(json.dumps(t, cls=NummusJSONEncoder)))
    target = {"transactions": transactions}
    self.assertEqual(target, result)
