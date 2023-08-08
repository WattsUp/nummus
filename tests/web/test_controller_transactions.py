"""Test module nummus.web.controller_transactions
"""

import datetime
import uuid

import simplejson

from nummus.models import (Account, AccountCategory, Asset, AssetCategory,
                           NummusJSONEncoder, Transaction, TransactionCategory,
                           TransactionSplit, TxnList)

from tests.web.base import WebTestBase


class TestControllerTransactions(WebTestBase):
  """Test controller_transactions methods
  """

  def test_create(self):
    p = self._portfolio

    today = datetime.date.today()

    with p.get_session() as s:
      # Create accounts
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      asset = Asset(name="bananas", category=AssetCategory.ITEM)
      s.add_all((acct, asset))
      s.commit()
      acct_uuid = acct.uuid
      asset_uuid = asset.uuid

    # Make the minimum
    total = self.random_decimal(-10, 10)
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
      self.assertEqual(total, txn.total)
      self.assertEqual(statement, txn.statement)
      self.assertTrue(txn.locked, "Transaction is not locked")
      self.assertEqual(1, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqual(total, t_split.total)

      # Serialize then deserialize
      json_s = simplejson.dumps(txn, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)

      s.delete(t_split)
      s.delete(txn)
      s.commit()
    self.assertDictEqual(target, result)

    # Make the maximum
    total = self.random_decimal(-10, 0)
    sales_tax = self.random_decimal(-10, 0)
    statement = self.random_string()
    payee = self.random_string()
    description = self.random_string()
    category = TransactionCategory.FOOD
    subcategory = self.random_string()
    tag = self.random_string()
    asset_qty = self.random_decimal(-1, 1)
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
      txn: Transaction = s.query(Transaction).first()
      self.assertEqual(f"/api/transactions/{txn.uuid}", headers["Location"])

      self.assertEqual(acct, txn.account)
      self.assertEqual(today, txn.date)
      self.assertEqual(total, txn.total)
      self.assertEqual(statement, txn.statement)
      self.assertTrue(txn.locked, "Transaction is not locked")
      self.assertEqual(1, len(txn.splits))
      t_split = txn.splits[0]
      self.assertEqual(total, t_split.total)
      self.assertEqual(sales_tax, t_split.sales_tax)
      self.assertEqual(payee, t_split.payee)
      self.assertEqual(description, t_split.description)
      self.assertEqual(category, t_split.category)
      self.assertEqual(subcategory, t_split.subcategory)
      self.assertEqual(tag, t_split.tag)
      self.assertEqual(asset, t_split.asset)
      self.assertEqual(asset_qty, t_split.asset_quantity)

      # Serialize then deserialize
      json_s = simplejson.dumps(txn, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)
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

    # Wrong Content-Type
    self.api_post(endpoint,
                  data="raw",
                  headers={"Content-Type": "text/plain"},
                  rc=415)

  def test_get(self):
    p = self._portfolio

    today = datetime.date.today()

    with p.get_session() as s:
      # Create accounts and transactions
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      s.add(acct)
      s.commit()

      txn = Transaction(account=acct,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=100, parent=txn)
      s.add_all((txn, t_split))
      s.commit()
      t_uuid = txn.uuid

      # Serialize then deserialize
      json_s = simplejson.dumps(txn, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)
    endpoint = f"/api/transactions/{t_uuid}"

    # Get by uuid
    result, _ = self.api_get(endpoint)
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    today = datetime.date.today()

    with p.get_session() as s:
      # Create accounts and transactions
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      asset = Asset(name="bananas", category=AssetCategory.ITEM)
      s.add_all((acct, asset))
      s.commit()
      asset_uuid = asset.uuid

      txn = Transaction(account=acct,
                        date=today,
                        total=-100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=txn.total, parent=txn)
      s.add_all((txn, t_split))
      s.commit()
      t_uuid = txn.uuid

      # Serialize then deserialize
      json_s = simplejson.dumps(txn, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)
    endpoint = f"/api/transactions/{t_uuid}"

    # Update
    new_statement = self.random_string()
    new_date = today - datetime.timedelta(days=1)
    new_category_0 = TransactionCategory.SERVICES
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    target["splits"][0]["category"] = new_category_0.name.lower()
    target["splits"][0]["date"] = new_date.isoformat()
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req.pop("uuid")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req_split_0.pop("account_uuid")
    req_split_0.pop("date")
    req_split_0.pop("locked")
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
    new_category_0 = TransactionCategory.FOOD
    new_category_1 = TransactionCategory.HOBBIES
    target["statement"] = new_statement
    target["date"] = new_date.isoformat()
    # Duplicate split
    target["splits"].append(dict(target["splits"][0]))
    target["splits"][0]["category"] = new_category_0.name.lower()
    target["splits"][1]["category"] = new_category_1.name.lower()
    target["splits"][1]["asset_uuid"] = asset_uuid
    req = dict(target)
    req_split_0 = dict(target["splits"][0])
    req_split_1 = dict(target["splits"][1])
    req.pop("uuid")
    req_split_0.pop("uuid")
    req_split_0.pop("parent_uuid")
    req_split_0.pop("account_uuid")
    req_split_0.pop("date")
    req_split_0.pop("locked")
    req_split_1.pop("uuid")
    req_split_1.pop("parent_uuid")
    req_split_1.pop("account_uuid")
    req_split_1.pop("date")
    req_split_1.pop("locked")
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
    new_category_0 = TransactionCategory.TRAVEL
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
    req_split_0.pop("account_uuid")
    req_split_0.pop("date")
    req_split_0.pop("locked")
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

    # Wrong Content-Type
    self.api_put(endpoint,
                 data="raw",
                 headers={"Content-Type": "text/plain"},
                 rc=415)

  def test_delete(self):
    p = self._portfolio

    today = datetime.date.today()

    with p.get_session() as s:
      # Create accounts and transactions
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      s.add(acct)
      s.commit()

      txn = Transaction(account=acct,
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

    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    tomorrow = today + datetime.timedelta(days=1)
    subcategory = self.random_string()
    tag = self.random_string()

    with p.get_session() as s:
      # Create accounts
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      acct_invest = Account(name="Monkey Investments",
                            institution="Ape Trading",
                            category=AccountCategory.INVESTMENT)
      asset = Asset(name="Banana", category=AssetCategory.ITEM)
      s.add_all((acct_checking, acct_invest, asset))
      s.commit()

      acct_invest_uuid = acct_invest.uuid
      asset_uuid = asset.uuid

      transactions: TxnList = []

      for i, category in enumerate([
          TransactionCategory.HOME, TransactionCategory.FOOD,
          TransactionCategory.SHOPPING, TransactionCategory.HOBBIES,
          TransactionCategory.SERVICES, TransactionCategory.TRAVEL
      ]):
        txn = Transaction(account=acct_checking,
                          date=today,
                          total=-100,
                          statement=self.random_string())
        t_split = TransactionSplit(total=txn.total,
                                   parent=txn,
                                   category=category,
                                   payee=self.random_string(),
                                   description=self.random_string(),
                                   subcategory=self.random_string(),
                                   tag=self.random_string())
        if i == 5:
          txn.account = acct_invest
          txn.date = yesterday
          txn.locked = True
          t_split.asset = asset
        s.add_all((txn, t_split))
        transactions.append(txn)
      s.commit()

      # Split t0
      t_split_extra_0 = TransactionSplit(total=-10,
                                         parent=transactions[0],
                                         category=TransactionCategory.HOBBIES,
                                         payee=self.random_string(),
                                         description=self.random_string(),
                                         subcategory=self.random_string(),
                                         tag=tag)
      t_split_extra_1 = TransactionSplit(total=-10,
                                         parent=transactions[0],
                                         category=TransactionCategory.HOBBIES,
                                         payee=self.random_string(),
                                         description=self.random_string(),
                                         subcategory=subcategory,
                                         tag=self.random_string())
      s.add_all((t_split_extra_0, t_split_extra_1))

      s.commit()
      # Sort by date, then parent, then id
      query = s.query(TransactionSplit).order_by(TransactionSplit.date,
                                                 TransactionSplit.parent_id,
                                                 TransactionSplit.id)
      # Serialize then deserialize
      json_s = simplejson.dumps(query.all(),
                                cls=NummusJSONEncoder,
                                use_decimal=True)
      t_splits = simplejson.loads(json_s, use_decimal=True)
      n_splits = len(t_splits)
    endpoint = "/api/transactions"

    # Get all
    result, _ = self.api_get(endpoint)
    target = {"transactions": t_splits, "count": n_splits, "next_offset": None}
    self.assertEqual(target, result)

    # Get only HOBBIES
    result, _ = self.api_get(endpoint, {"category": "hobbies"})
    target = {
        "transactions": [
            t_split for t_split in t_splits if t_split["category"] == "hobbies"
        ],
        "count": 3,
        "next_offset": None
    }
    self.assertEqual(target, result)

    # Sort by newest first
    result, _ = self.api_get(endpoint, {"sort": "newest"})
    target = {
        "transactions": t_splits[1:] + t_splits[:1],
        "count": n_splits,
        "next_offset": None
    }
    self.assertEqual(target, result)

    # Filter by start date
    result, _ = self.api_get(endpoint, {"start": today, "end": tomorrow})
    target = {
        "transactions": t_splits[1:],
        "count": n_splits - 1,
        "next_offset": None
    }
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

    # Unknown asset
    self.api_get(endpoint, {"asset": uuid.uuid4()}, rc=404)

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
    self.api_get(endpoint, {"category": "invalid"}, rc=400)

    # Get via paging
    result, _ = self.api_get(endpoint, {"limit": 1})
    target = {
        "transactions": [t_splits[0]],
        "count": n_splits,
        "next_offset": 1
    }
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"limit": 1, "offset": n_splits - 1})
    target = {
        "transactions": [t_splits[-1]],
        "count": n_splits,
        "next_offset": None
    }
    self.assertEqual(target, result)
