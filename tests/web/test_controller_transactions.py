"""Test module nummus.web.controller_transactions
"""

import typing as t

import datetime
import json
from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           NummusJSONEncoder, Transaction, TransactionCategory,
                           TransactionSplit)

from tests.web.base import WebTestBase


class TestControllerTransactions(WebTestBase):
  """Test controller_transactions methods
  """

  def test_create(self):
    p = self._portfolio

    # Create accounts
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH)
    asset = Asset(name="bananas", category=AssetCategory.ITEM)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add_all((acct, asset))
      s.commit()
      acct_uuid = acct.uuid
      asset_uuid = asset.uuid

    # Make the minimum
    total = float(self._RNG.uniform(-10, 10))
    statement = self.random_string()
    req = {
        "account_uuid": acct_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True,
        "splits": [{
            "total": total
        }]
    }
    endpoint = "/api/transactions"
    result, headers = self.api_post(endpoint, json=req)
    with p.get_session() as s:
      txn = s.query(Transaction).first()
      self.assertEqual(f"/api/transactions/{txn.uuid}", headers["Location"])

      self.assertEqual(acct, txn.account)
      self.assertEqual(today, txn.date)
      self.assertEqualWithinError(total, txn.total, 1e-6)
      self.assertEqual(statement, txn.statement)
      self.assertTrue(txn.locked, "Transaction is not locked")
      self.assertEqual(1, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqualWithinError(total, t_split.total, 1e-6)

      # Serialize then deserialize
      target = json.loads(json.dumps(txn, cls=NummusJSONEncoder))

      s.delete(t_split)
      s.delete(txn)
      s.commit()
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
    req_split = {
        "total": total,
        "sales_tax": sales_tax,
        "payee": payee,
        "description": description,
        "category": category.name.lower(),
        "subcategory": subcategory,
        "tag": tag,
        "asset_uuid": asset_uuid,
        "asset_quantity": asset_qty
    }
    req = {
        "account_uuid": acct_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True,
        "splits": [req_split]
    }

    result, headers = self.api_post(endpoint, json=req)
    with p.get_session() as s:
      txn = s.query(Transaction).first()
      self.assertEqual(f"/api/transactions/{txn.uuid}", headers["Location"])

      self.assertEqual(acct, txn.account)
      self.assertEqual(today, txn.date)
      self.assertEqualWithinError(total, txn.total, 1e-6)
      self.assertEqual(statement, txn.statement)
      self.assertTrue(txn.locked, "Transaction is not locked")
      self.assertEqual(1, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqualWithinError(total, t_split.total, 1e-6)
      self.assertEqualWithinError(sales_tax, t_split.sales_tax, 1e-6)
      self.assertEqual(payee, t_split.payee)
      self.assertEqual(description, t_split.description)
      self.assertEqual(category, t_split.category)
      self.assertEqual(subcategory, t_split.subcategory)
      self.assertEqual(tag, t_split.tag)
      self.assertEqual(asset, t_split.asset)
      self.assertEqual(asset_qty, t_split.asset_quantity)

      # Serialize then deserialize
      target = json.loads(json.dumps(txn, cls=NummusJSONEncoder))
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {
        "account_uuid": acct_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True
    }
    self.api_post(endpoint, json=req, rc=400)

    # Need at least one split
    req = {
        "account_uuid": acct_uuid,
        "date": today.isoformat(),
        "total": total,
        "statement": statement,
        "locked": True,
        "splits": []
    }
    self.api_post(endpoint, json=req, rc=422)

  def test_get(self):
    p = self._portfolio

    # Create accounts and transactions
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(acct)
      s.commit()

      txn = Transaction(account_id=acct.id,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=txn)
      s.add_all((txn, t_split))
      s.commit()
      t_uuid = txn.uuid
      target = json.loads(json.dumps(txn, cls=NummusJSONEncoder))
    endpoint = f"/api/transactions/{t_uuid}"

    # Get by uuid
    result, _ = self.api_get(endpoint)
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    # Create accounts and transactions
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH)
    asset = Asset(name="bananas", category=AssetCategory.ITEM)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add_all((acct, asset))
      s.commit()
      asset_uuid = asset.uuid

      txn = Transaction(account_id=acct.id,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=txn)
      s.add_all((txn, t_split))
      s.commit()
      t_uuid = txn.uuid
      target = json.loads(json.dumps(txn, cls=NummusJSONEncoder))
    endpoint = f"/api/transactions/{t_uuid}"

    # Update
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = self._RNG.choice(TransactionCategory)
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    target["splits"][0]["category"] = new_category_0.name.lower()
    target["splits"][0]["date"] = new_date.isoformat()
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req.pop("uuid")
    req.pop("is_split")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req_split_0.pop("account_uuid")
    req_split_0.pop("date")
    req_split_0.pop("locked")
    req_split_0.pop("is_split")
    req["splits"] = [req_split_0]
    result, _ = self.api_put(endpoint, json=req)
    with p.get_session() as s:
      txn = s.query(Transaction).where(Transaction.uuid == t_uuid).first()
      self.assertEqual(new_statement, txn.statement)
      self.assertEqual(new_date, txn.date)
      self.assertEqual(1, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqual(new_category_0, t_split.category)

      # Check no other splits were created
      n_splits = s.query(TransactionSplit).count()
      self.assertEqual(1, n_splits)
    self.assertEqual(target, result)

    # Update and add a split
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = self._RNG.choice(TransactionCategory)
    new_category_1 = self._RNG.choice(TransactionCategory)
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    # Duplicate split
    target["is_split"] = True
    target["splits"].append(dict(target["splits"][0]))
    target["splits"][0]["category"] = new_category_0.name.lower()
    target["splits"][0]["is_split"] = True
    target["splits"][1]["category"] = new_category_1.name.lower()
    target["splits"][1]["asset_uuid"] = asset_uuid
    target["splits"][1]["is_split"] = True
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req_split_1 = dict(target["splits"][1])
    req.pop("uuid")
    req.pop("is_split")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req_split_0.pop("account_uuid")
    req_split_0.pop("date")
    req_split_0.pop("locked")
    req_split_0.pop("is_split")
    req_split_1.pop("uuid")
    req_split_1.pop("parent_uuid")
    req_split_1.pop("account_uuid")
    req_split_1.pop("date")
    req_split_1.pop("locked")
    req_split_1.pop("is_split")
    req["splits"] = [req_split_0, req_split_1]
    result, _ = self.api_put(endpoint, json=req)
    with p.get_session() as s:
      txn = s.query(Transaction).where(Transaction.uuid == t_uuid).first()
      self.assertEqual(new_statement, txn.statement)
      self.assertEqual(new_date, txn.date)
      self.assertEqual(2, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqual(new_category_0, t_split.category)
      t_split = txn.splits[1]
      self.assertEqual(new_category_1, t_split.category)
      self.assertEqual(asset_uuid, t_split.asset_uuid)

      # Update target t_split_1 uuid since it is new
      target["splits"][1]["uuid"] = t_split.uuid

      # Check first split was reused
      n_splits = s.query(TransactionSplit).count()
      self.assertEqual(2, n_splits)
    self.assertEqual(target, result)

    # Update and remove a split
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = self._RNG.choice(TransactionCategory)
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    # Keep only the second one
    target["is_split"] = False
    target["splits"] = [target["splits"][1]]
    target["splits"][0]["category"] = new_category_0.name.lower()
    target["splits"][0]["is_split"] = False
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req.pop("uuid")
    req.pop("is_split")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req_split_0.pop("account_uuid")
    req_split_0.pop("date")
    req_split_0.pop("locked")
    req_split_0.pop("is_split")
    req["splits"] = [req_split_0]
    result, _ = self.api_put(endpoint, json=req)
    with p.get_session() as s:
      txn = s.query(Transaction).where(Transaction.uuid == t_uuid).first()
      self.assertEqual(new_statement, txn.statement)
      self.assertEqual(new_date, txn.date)
      self.assertEqual(1, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqual(new_category_0, t_split.category)

      # Update target t_split_0 uuid since it might be different
      target["splits"][0]["uuid"] = t_split.uuid

      # Check other split was deleted
      n_splits = s.query(TransactionSplit).count()
      self.assertEqual(1, n_splits)
    self.assertEqual(target, result)

    # Try to remove all splits
    req["splits"] = []
    self.api_put(endpoint, json=req, rc=422)

    # Read only properties
    self.api_put(endpoint, json=target, rc=400)

  def test_delete(self):
    p = self._portfolio

    # Create accounts and transactions
    acct = Account(name="Monkey Bank Checking",
                   institution="Monkey Bank",
                   category=AccountCategory.CASH)
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(acct)
      s.commit()

      txn = Transaction(account_id=acct.id,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=txn)
      s.add_all((txn, t_split))
      s.commit()
      t_uuid = txn.uuid
    endpoint = f"/api/transactions/{t_uuid}"

    with p.get_session() as s:
      result = s.query(Transaction).count()
      self.assertEqual(1, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(1, result)

    # Delete by uuid
    self.api_delete(endpoint)

    with p.get_session() as s:
      result = s.query(Transaction).count()
      self.assertEqual(0, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    p = self._portfolio

    # Create accounts
    acct_checking = Account(name="Monkey Bank Checking",
                            institution="Monkey Bank",
                            category=AccountCategory.CASH)
    acct_invest = Account(name="Monkey Investments",
                          institution="Ape Trading",
                          category=AccountCategory.INVESTMENT)
    asset = Asset(name="Banana", category=AssetCategory.ITEM)
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    subcategory = self.random_string()
    tag = self.random_string()
    with p.get_session() as s:
      s.add_all((acct_checking, acct_invest, asset))
      s.commit()

      acct_invest_uuid = acct_invest.uuid
      asset_uuid = asset.uuid

      transactions: t.List[Transaction] = []
      for category in TransactionCategory:
        txn = Transaction(account=acct_checking,
                          date=today,
                          total=100,
                          statement=self.random_string())
        t_split = TransactionSplit(total=100,
                                   parent=txn,
                                   category=category,
                                   payee=self.random_string(),
                                   description=self.random_string(),
                                   subcategory=self.random_string(),
                                   tag=self.random_string())
        s.add_all((txn, t_split))
        transactions.append(txn)

      transactions[-1].account = acct_invest
      transactions[-1].date = yesterday
      transactions[-1].locked = True
      transactions[-1].splits[0].asset = asset

      # Split t0
      t_split_extra_0 = TransactionSplit(total=10,
                                         parent=transactions[0],
                                         category=TransactionCategory.TRAVEL,
                                         payee=self.random_string(),
                                         description=self.random_string(),
                                         subcategory=self.random_string(),
                                         tag=tag)
      t_split_extra_1 = TransactionSplit(total=10,
                                         parent=transactions[0],
                                         category=TransactionCategory.TRAVEL,
                                         payee=self.random_string(),
                                         description=self.random_string(),
                                         subcategory=subcategory,
                                         tag=self.random_string())
      s.add_all((t_split_extra_0, t_split_extra_1))

      s.commit()
      # Sort by date, then parent, then id
      query = s.query(TransactionSplit).join(Transaction).order_by(
          Transaction.date, TransactionSplit.parent_id, TransactionSplit.id)
      t_splits = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    endpoint = "/api/transactions"

    # Get all
    result, _ = self.api_get(endpoint)
    target = {"transactions": t_splits, "count": 11, "next_offset": None}
    self.assertEqual(target, result)

    # Get only travel
    result, _ = self.api_get(endpoint, {"category": "travel"})
    target = {
        "transactions": [t_splits[2], t_splits[3], t_splits[8]],
        "count": 3,
        "next_offset": None
    }
    self.assertEqual(target, result)

    # Sort by newest first
    result, _ = self.api_get(endpoint, {"sort": "newest"})
    target = {
        "transactions": t_splits[1:] + t_splits[:1],
        "count": 11,
        "next_offset": None
    }
    self.assertEqual(target, result)

    # Filter by start date
    result, _ = self.api_get(endpoint, {"start": today, "end": tomorrow})
    target = {"transactions": t_splits[1:], "count": 10, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by end date
    result, _ = self.api_get(endpoint, {"end": yesterday})
    target = {"transactions": t_splits[:1], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)

    # Filter by subcategory
    result, _ = self.api_get(endpoint, {"subcategory": subcategory})
    target = {"transactions": [t_splits[3]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by tag
    result, _ = self.api_get(endpoint, {"tag": tag})
    target = {"transactions": [t_splits[2]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by locked
    result, _ = self.api_get(endpoint, {"locked": True})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by account
    result, _ = self.api_get(endpoint, {"account": acct_invest_uuid})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by account category
    result, _ = self.api_get(endpoint, {"account_category": "investment"})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by asset
    result, _ = self.api_get(endpoint, {"asset": asset_uuid})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Filter by asset category
    result, _ = self.api_get(endpoint, {"asset_category": "item"})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by payee
    result, _ = self.api_get(endpoint, {"search": t_splits[0]["payee"]})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by description
    result, _ = self.api_get(endpoint, {"search": t_splits[0]["description"]})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by subcategory
    result, _ = self.api_get(endpoint, {"search": t_splits[0]["subcategory"]})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Search by tag
    result, _ = self.api_get(endpoint, {"search": t_splits[0]["tag"]})
    target = {"transactions": [t_splits[0]], "count": 1, "next_offset": None}
    self.assertEqual(target, result)

    # Strict query validation
    self.api_get(endpoint, {"fake": "invalid"}, rc=400)
