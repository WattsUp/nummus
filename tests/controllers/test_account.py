"""Test module nummus.controllers.account
"""

import datetime

from nummus import custom_types as t
from nummus.models import (Account, AccountCategory, Transaction,
                           TransactionCategory, TransactionSplit)

from tests.controllers.base import WebTestBase


class TestAccount(WebTestBase):
  """Test account controller
  """

  def test_edit(self):
    p = self._portfolio

    today = datetime.date.today()

    with p.get_session() as s:
      acct = Account(name="Monkey Bank Checking",
                     institution="Monkey Bank",
                     category=AccountCategory.CASH,
                     closed=False)
      s.add(acct)
      s.commit()

      acct_uuid = acct.uuid

      categories: t.Dict[str, TransactionCategory] = {
          cat.name: cat for cat in s.query(TransactionCategory).all()
      }
      t_cat = categories["Uncategorized"]

      txn = Transaction(account_id=acct.id,
                        date=today,
                        amount=100,
                        statement=self.random_string())
      t_split = TransactionSplit(amount=txn.amount,
                                 parent=txn,
                                 category_id=t_cat.id)
      s.add_all((txn, t_split))

      s.commit()

    endpoint = f"/h/accounts/a/{acct_uuid}/edit"
    result, _ = self.api_get(endpoint, content_type="text/html; charset=utf-8")
    self.assertValidHTML(result)

    name = self.random_string()
    institution = self.random_string()
    form = {"institution": institution, "name": name, "category": "credit"}
    result, _ = self.api_post(endpoint,
                              content_type="text/html; charset=utf-8",
                              data=form)
    self.assertValidHTML(result)
    with p.get_session() as s:
      acct = s.query(Account).first()
      self.assertEqual(acct.name, name)
      self.assertEqual(acct.institution, institution)
      self.assertEqual(acct.category, AccountCategory.CREDIT)
      self.assertFalse(acct.closed)

    form = {
        "institution": institution,
        "name": name,
        "category": "credit",
        "closed": ""
    }
    result, _ = self.api_post(endpoint,
                              content_type="text/html; charset=utf-8",
                              data=form)
    e_str = "Cannot close Account with non-zero balance"
    self.assertIn(e_str, result)
    with p.get_session() as s:
      self.assertFalse(acct.closed)
