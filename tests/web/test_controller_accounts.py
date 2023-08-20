"""Test module nummus.web.controller_accounts
"""

import datetime

import simplejson

from nummus.models import (Account, AccountCategory, NummusJSONEncoder,
                           Transaction, TransactionSplit, TxnSplitList)

from tests.web.base import WebTestBase


class TestControllerAccounts(WebTestBase):
  """Test controller_accounts methods
  """

  def test_create(self):
    p = self._portfolio

    name = self.random_string()
    institution = self.random_string()
    category = self._RNG.choice(AccountCategory)

    req = {"name": name, "institution": institution, "category": category}
    endpoint = "/api/accounts"
    result, headers = self.api_post(endpoint, json=req)
    with p.get_session() as s:
      acct = s.query(Account).first()
      self.assertEqual(f"/api/accounts/{acct.uuid}", headers["Location"])

      # Serialize then deserialize
      json_s = simplejson.dumps(acct, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)

    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"name": name, "institution": institution}
    self.api_post(endpoint, json=req, rc=400)

    # Wrong Content-Type
    self.api_post(endpoint,
                  data="raw",
                  headers={"Content-Type": "text/plain"},
                  rc=415)

  def test_get(self):
    p = self._portfolio

    with p.get_session() as s:
      # Create accounts
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      s.add(acct)
      s.commit()

      acct_uuid = acct.uuid

      # Serialize then deserialize
      json_s = simplejson.dumps(acct, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)
    endpoint = f"/api/accounts/{acct_uuid}"

    # Get by uuid
    result, _ = self.api_get(endpoint)
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    with p.get_session() as s:
      # Create accounts
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      s.add(acct)
      s.commit()

      acct_uuid = acct.uuid

      # Serialize then deserialize
      json_s = simplejson.dumps(acct, cls=NummusJSONEncoder, use_decimal=True)
      target = simplejson.loads(json_s, use_decimal=True)
    endpoint = f"/api/accounts/{acct_uuid}"

    # Update by uuid
    new_name = self.random_string()
    new_category = AccountCategory.CREDIT
    target["name"] = new_name
    target["category"] = new_category.name.lower()
    req = dict(target)
    req.pop("uuid")
    req.pop("opened_on")
    req.pop("updated_on")
    result, _ = self.api_put(endpoint, json=req)
    with p.get_session() as s:
      acct = s.query(Account).where(Account.uuid == acct_uuid).first()
      self.assertEqual(new_name, acct.name)
      self.assertEqual(new_category, acct.category)
    self.assertEqual(target, result)

    # Read only properties
    self.api_put(endpoint, json=target, rc=400)

    # Wrong Content-Type
    self.api_put(endpoint,
                 data="raw",
                 headers={"Content-Type": "text/plain"},
                 rc=415)

  def test_delete(self):
    p = self._portfolio

    n_transactions = 10
    today = datetime.date.today()

    with p.get_session() as s:
      # Create accounts
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH)
      s.add(acct)
      s.commit()

      for _ in range(n_transactions):
        txn = Transaction(account=acct,
                          date=today,
                          total=100,
                          statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=txn)
        s.add_all((txn, t_split))
      s.commit()

      acct_uuid = acct.uuid
    endpoint = f"/api/accounts/{acct_uuid}"

    with p.get_session() as s:
      result = s.query(Account).count()
      self.assertEqual(1, result)
      result = s.query(Transaction).count()
      self.assertEqual(n_transactions, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(n_transactions, result)

    # Delete by uuid
    self.api_delete(endpoint)

    with p.get_session() as s:
      result = s.query(Account).count()
      self.assertEqual(0, result)
      result = s.query(Transaction).count()
      self.assertEqual(0, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    p = self._portfolio

    with p.get_session() as s:
      # Create accounts
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      acct_invest = Account(name="Gorilla Investments",
                            institution="Ape Trading",
                            category=AccountCategory.INVESTMENT)
      s.add_all((acct_checking, acct_invest))
      s.commit()
      query = s.query(Account)

      # Serialize then deserialize
      json_s = simplejson.dumps(query.all(),
                                cls=NummusJSONEncoder,
                                use_decimal=True)
      accounts = simplejson.loads(json_s, use_decimal=True)
    endpoint = "/api/accounts"

    # Get all
    result, _ = self.api_get(endpoint)
    target = {"accounts": accounts, "count": 2}
    self.assertEqual(target, result)

    # Get only cash
    result, _ = self.api_get(endpoint, {"category": "cash"})
    target = {"accounts": [accounts[0]], "count": 1}
    self.assertEqual(target, result)

    # Search by institution
    result, _ = self.api_get(endpoint, {"search": "Money Bank"})
    target = {"accounts": [accounts[0]], "count": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"search": "Ape Trading"})
    target = {"accounts": [accounts[1]], "count": 1}
    self.assertEqual(target, result)

    # Search by bank
    result, _ = self.api_get(endpoint, {"search": "Investments"})
    target = {"accounts": [accounts[1]], "count": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"search": "checking"})
    target = {"accounts": [accounts[0]], "count": 1}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"search": "Monkey Gorilla"})
    target = {"accounts": accounts, "count": 2}
    self.assertEqual(target, result)

    # Strict query validation
    self.api_get(endpoint, {"category": "invalid"}, rc=400)

  def test_get_transactions(self):
    p = self._portfolio

    n_transactions = 10
    today = datetime.date.today()

    with p.get_session() as s:
      # Create accounts
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      acct_invest = Account(name="Monkey Investments",
                            institution="Ape Trading",
                            category=AccountCategory.INVESTMENT)
      s.add_all((acct_checking, acct_invest))
      s.commit()

      for _ in range(n_transactions):
        txn = Transaction(account=acct_checking,
                          date=today,
                          total=100,
                          statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=txn)
        s.add_all((txn, t_split))

      for _ in range(n_transactions):
        txn = Transaction(account=acct_invest,
                          date=today,
                          total=100,
                          statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=txn)
        s.add_all((txn, t_split))
      s.commit()

      # Sort by date, then parent, then id
      query = s.query(TransactionSplit).where(
          TransactionSplit.account_id == acct_checking.id)
      t_splits_obj: TxnSplitList = query.all()

      # Serialize then deserialize
      json_s = simplejson.dumps(t_splits_obj,
                                cls=NummusJSONEncoder,
                                use_decimal=True)
      t_splits = simplejson.loads(json_s, use_decimal=True)

      acct_uuid = acct_checking.uuid
    endpoint = f"/api/accounts/{acct_uuid}/transactions"

    result, _ = self.api_get(endpoint)
    target = {
        "transactions": t_splits,
        "count": n_transactions,
        "next_offset": None
    }
    self.assertEqual(target, result)

    result_other_way, _ = self.api_get("/api/transactions",
                                       {"account": acct_uuid})
    self.assertEqual(result, result_other_way)

  def test_get_value(self):
    p = self._portfolio

    n_transactions = 10
    today = datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)

    with p.get_session() as s:
      # Create accounts
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      s.add(acct_checking)
      s.commit()

      value = 0
      for _ in range(n_transactions):
        txn = Transaction(account=acct_checking,
                          date=today,
                          total=self.random_decimal(-10, 10),
                          statement=self.random_string())
        t_split = TransactionSplit(total=txn.total, parent=txn)
        value += txn.total
        s.add_all((txn, t_split))
      s.commit()

      acct_uuid = acct_checking.uuid
    endpoint = f"/api/accounts/{acct_uuid}/value"

    result, _ = self.api_get(endpoint)
    target = {"values": [value], "dates": [today.isoformat()]}
    self.assertEqual(target, result)

    result, _ = self.api_get(endpoint, {"start": yesterday, "end": today})
    target = {
        "values": [0, value],
        "dates": [yesterday.isoformat(),
                  today.isoformat()]
    }
    self.assertEqual(target, result)

    # Invalid date filters
    self.api_get(endpoint, {"start": today, "end": yesterday}, rc=422)
