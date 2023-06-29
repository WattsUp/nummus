"""Test module nummus.web.controller_account
"""

import datetime
import io
import json
from unittest import mock
import warnings

from nummus import portfolio
from nummus.models import (Account, AccountCategory, NummusJSONEncoder,
                           Transaction, TransactionSplit)

from tests.base import TestBase


class TestControllerAccount(TestBase):
  """Test controller_account methods
  """

  def test_create(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    name = self.random_string()
    institution = self.random_string()
    category = self._RNG.choice(AccountCategory)

    req = {"name": name, "institution": institution, "category": category}

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.post("/api/account", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    with p.get_session() as s:
      a = s.query(Account).first()
      # Serialize then deserialize
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    result = response.json
    self.assertDictEqual(target, result)

    # Fewer keys are bad
    req = {"name": name, "institution": institution}
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.post("/api/account", json=req)
    self.assertEqual(400, response.status_code)

  def test_get(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    # Get by uuid
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get(f"/api/account/{a_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

  def test_update(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts
    a = Account(name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH)
    with p.get_session() as s:
      s.add(a)
      s.commit()

      a_uuid = a.uuid
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    # Update by uuid
    new_name = self.random_string()
    new_category = AccountCategory.CREDIT
    target["name"] = new_name
    target["category"] = new_category.name.lower()
    req = dict(target)
    req.pop("uuid")
    req.pop("opened_on")
    req.pop("updated_on")
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.put(f"/api/account/{a_uuid}", json=req)
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    with p.get_session() as s:
      a = s.query(Account).where(Account.uuid == a_uuid).first()
      self.assertEqual(new_name, a.name)
      self.assertEqual(new_category, a.category)
    result = response.json
    self.assertEqual(target, result)

    # Read only properties
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.put(f"/api/account/{a_uuid}", json=target)
    self.assertEqual(400, response.status_code)

  def test_delete(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

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
      target = json.loads(json.dumps(a, cls=NummusJSONEncoder))

    with p.get_session() as s:
      result = s.query(Account).count()
      self.assertEqual(1, result)
      result = s.query(Transaction).count()
      self.assertEqual(n_transactions, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(n_transactions, result)

    # Delete by uuid
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.delete(f"/api/account/{a_uuid}")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)
    result = response.json
    self.assertEqual(target, result)

    with p.get_session() as s:
      result = s.query(Account).count()
      self.assertEqual(0, result)
      result = s.query(Transaction).count()
      self.assertEqual(0, result)
      result = s.query(TransactionSplit).count()
      self.assertEqual(0, result)

  def test_get_all(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    # Create accounts
    a_checking = Account(name="Monkey Bank Checking",
                         institution="Monkey Bank",
                         category=AccountCategory.CASH)
    a_invest = Account(name="Monkey Investments",
                       institution="Monkey Bank",
                       category=AccountCategory.INVESTMENT)
    with p.get_session() as s:
      s.add_all((a_checking, a_invest))
      s.commit()

    # Get all
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/accounts")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Account)
      accounts = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    target = {"accounts": accounts}
    self.assertEqual(target, result)

    # Get only cash
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/accounts?category=cash")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Account).where(Account.category == AccountCategory.CASH)
      accounts = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    target = {"accounts": accounts}
    self.assertEqual(target, result)

    # Strict query validation
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.get("/api/accounts?fake=invalid")
    self.assertEqual(400, response.status_code)
