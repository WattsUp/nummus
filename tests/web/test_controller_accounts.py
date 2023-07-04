"""Test module nummus.web.controller_accounts
"""

import datetime
import json
from nummus.models import (Account, AccountCategory, NummusJSONEncoder,
                           Transaction, TransactionSplit)

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
      a = s.query(Account).first()
      self.assertEqual(f"/api/accounts/{a.uuid}", headers["Location"])

      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"name": name, "institution": institution}
    self.api_post(endpoint, json=req, rc=400)

  def test_get(self):
    p = self._portfolio

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))
    endpoint = f"/api/accounts/{a_uuid}"

    # Get by uuid
    result, _ = self.api_get(endpoint)
    self.assertEqual(target, result)

  def test_update(self):
    p = self._portfolio

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))
    endpoint = f"/api/accounts/{a_uuid}"

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
      a = s.query(Account).where(Account.uuid == a_uuid).first()
      self.assertEqual(new_name, a.name)
      self.assertEqual(new_category, a.category)
    self.assertEqual(target, result)

    # Read only properties
    self.api_put(endpoint, json=target, rc=400)

  def test_delete(self):
    p = self._portfolio

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    n_transactions = 10
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a)
      s.commit()

      for _ in range(n_transactions):
        t = Transaction(account_id=a.id,
                        date=today,
                        total=100,
                        statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=t)
        s.add_all((t, t_split))
      s.commit()

      a_uuid = a.uuid
    endpoint = f"/api/accounts/{a_uuid}"

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

    # Create accounts
    a_checking = Account(name="Monkey Bank Checking",
                         institution="Monkey Bank",
                         category=AccountCategory.CASH)
    a_invest = Account(name="Monkey Investments",
                       institution="Ape Trading",
                       category=AccountCategory.INVESTMENT)
    with p.get_session() as s:
      s.add_all((a_checking, a_invest))
      s.commit()
      query = s.query(Account)
      accounts = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
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
    result, _ = self.api_get(endpoint, {"search": "Bank"})
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

    result, _ = self.api_get(endpoint, {"search": "Monkey"})
    target = {"accounts": accounts, "count": 2}
    self.assertEqual(target, result)

    # Strict query validation
    self.api_get(endpoint, {"sort": "invalid"}, rc=400)

  def test_get_transactions(self):
    p = self._portfolio

    # Create accounts
    a_checking = Account(name="Monkey Bank Checking",
                         institution="Monkey Bank",
                         category=AccountCategory.CASH)
    a_invest = Account(name="Monkey Investments",
                       institution="Ape Trading",
                       category=AccountCategory.INVESTMENT)
    n_transactions = 10
    today = datetime.date.today()
    with p.get_session() as s:
      s.add(a_checking)
      s.commit()

      for _ in range(n_transactions):
        t = Transaction(account=a_checking,
                        date=today,
                        total=100,
                        statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=t)
        s.add_all((t, t_split))

      for _ in range(n_transactions):
        t = Transaction(account=a_invest,
                        date=today,
                        total=100,
                        statement=self.random_string())
        t_split = TransactionSplit(total=100, parent=t)
        s.add_all((t, t_split))
      s.commit()

      # Sort by date, then parent, then id
      t_splits_obj = [t.splits[0] for t in a_checking.transactions]
      t_splits = json.loads(json.dumps(t_splits_obj, cls=NummusJSONEncoder))

      a_uuid = a_checking.uuid
    endpoint = f"/api/accounts/{a_uuid}/transactions"

    result, _ = self.api_get(endpoint)
    target = {
        "transactions": t_splits,
        "count": n_transactions,
        "next_offset": None
    }
    self.assertEqual(target, result)

    result_other_way, _ = self.api_get("/api/transactions", {"account": a_uuid})
    self.assertEqual(result, result_other_way)
