"""Test module nummus.web.controller_account
"""

import io
import json
from unittest import mock
import warnings

from nummus import portfolio
from nummus.models import Account, AccountCategory, NummusJSONEncoder

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

    # Extra keys are bad
    req = {
        "name": name,
        "institution": institution,
        "category": category,
        "extra": "key"
    }
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.post("/api/account", json=req)
    self.assertEqual(400, response.status_code)

    # Fewer keys are bad
    req = {"name": name, "institution": institution}
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.post("/api/account", json=req)
    self.assertEqual(400, response.status_code)

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

      target = [a_checking, a_invest]
      target = json.loads(json.dumps(target, cls=NummusJSONEncoder))

    # Get all
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/accounts")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    with p.get_session() as s:
      query = s.query(Account)
      target = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
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
      target = json.loads(json.dumps(query.all(), cls=NummusJSONEncoder))
    self.assertEqual(target, result)

    # Strict query validation
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      with mock.patch("sys.stderr", new=io.StringIO()) as _:
        response = client.get("/api/accounts?fake=invalid")
    self.assertEqual(400, response.status_code)
