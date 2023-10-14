"""Test module nummus.controllers.transaction
"""

import datetime

from nummus import custom_types as t
from nummus.models import (Account, AccountCategory, Transaction,
                           TransactionCategory, TransactionSplit)

from tests.controllers.base import WebTestBase


class TestTransaction(WebTestBase):
  """Test transaction controller
  """

  def _setup_portfolio(self) -> t.DictStr:
    """Create accounts and transactions to test with

    Returns:
      {
        "acct": Account name,
        "t_0": UUID for transaction 0
        "t_split_0": UUID for split 0
        "t_1": UUID for transaction 1
        "t_split_1": UUID for split 1
        "payee_0": Payee for transaction 0
        "payee_1": Payee for transaction 1
        "cat_0": Payee for transaction 0
        "cat_1": Payee for transaction 1
        "tag_1": Tag for transaction 1
      }
    """
    p = self._portfolio

    today = datetime.date.today()

    acct_name = "Monkey Bank Checking"
    payee_0 = "Apple"
    payee_1 = "Banana"

    cat_0 = "Interest"
    cat_1 = "Uncategorized"

    tag_1 = self.random_string()

    with p.get_session() as s:
      acct = Account(name=acct_name,
                     institution="Monkey Bank",
                     category=AccountCategory.CASH,
                     closed=False)
      s.add(acct)
      s.commit()

      categories = TransactionCategory.map_name(s)
      # Reverse categories for LUT
      categories = {v: k for k, v in categories.items()}

      txn = Transaction(account_id=acct.id,
                        date=today,
                        amount=100,
                        statement=self.random_string())
      t_split = TransactionSplit(amount=txn.amount,
                                 parent=txn,
                                 payee=payee_0,
                                 category_id=categories[cat_0])
      s.add_all((txn, t_split))
      s.commit()

      t_0_uuid = txn.uuid
      t_split_0_uuid = t_split.uuid

      txn = Transaction(account_id=acct.id,
                        date=today,
                        amount=-100,
                        statement=self.random_string(),
                        locked=True)
      t_split = TransactionSplit(amount=txn.amount,
                                 parent=txn,
                                 payee=payee_1,
                                 category_id=categories[cat_1],
                                 tag=tag_1)
      s.add_all((txn, t_split))
      s.commit()

      t_1_uuid = txn.uuid
      t_split_1_uuid = t_split.uuid

    return {
        "acct": acct_name,
        "t_0": t_0_uuid,
        "t_split_0": t_split_0_uuid,
        "t_1": t_1_uuid,
        "t_split_1": t_split_1_uuid,
        "payee_0": payee_0,
        "payee_1": payee_1,
        "cat_0": cat_0,
        "cat_1": cat_1,
        "tag_1": tag_1,
    }

  def test_page_all(self):
    endpoint = "/transactions"
    result, _ = self.web_get(endpoint)
    self.assertIn('id="txn-config"', result)
    self.assertIn('id="txn-paging"', result)
    self.assertIn('id="txn-header"', result)
    self.assertIn('id="txn-table"', result)
    self.assertIn("No matching transactions for given query filters", result)

  def test_table(self):
    d = self._setup_portfolio()

    payee_0 = d["payee_0"]
    payee_1 = d["payee_1"]
    cat_0 = d["cat_0"]
    tag_1 = d["tag_1"]

    endpoint = "/h/transactions/table"
    result, _ = self.web_get(endpoint)
    self.assertEqual(2, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_0}</div>', result)
    self.assertIn(f'<div class="col col-payee">{payee_1}</div>', result)

    queries = {"account": "Non selected", "period": "all"}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(0, result.count('<div class="col col-payee">'))
    self.assertIn("No matching transactions for given query filters", result)

    queries = {"payee": payee_0}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_0}</div>', result)

    queries = {"payee": "[blank]"}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(0, result.count('<div class="col col-payee">'))
    self.assertIn("No matching transactions for given query filters", result)

    queries = {"payee": ["[blank]", payee_1]}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_1}</div>', result)

    queries = {"category": cat_0}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_0}</div>', result)

    queries = {"tag": tag_1}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_1}</div>', result)

    queries = {"tag": "[blank]"}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_0}</div>', result)

    queries = {"tag": ["[blank]", tag_1]}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(2, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_0}</div>', result)
    self.assertIn(f'<div class="col col-payee">{payee_1}</div>', result)

    queries = {"locked": "true"}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_1}</div>', result)

    queries = {"search": payee_1}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(1, result.count('<div class="col col-payee">'))
    self.assertIn(f'<div class="col col-payee">{payee_1}</div>', result)

  def test_options(self):
    d = self._setup_portfolio()

    acct = d["acct"]
    payee_0 = d["payee_0"]
    payee_1 = d["payee_1"]
    cat_0 = d["cat_0"]
    cat_1 = d["cat_1"]
    tag_1 = d["tag_1"]

    endpoint = "/h/transactions/options/account"
    result, _ = self.web_get(endpoint)
    self.assertEqual(2, result.count("span"))
    self.assertIn(f"<span>{acct}</span>", result)

    endpoint = "/h/transactions/options/category"
    result, _ = self.web_get(endpoint, queries={"period": "all"})
    self.assertEqual(4, result.count("span"))
    self.assertIn(f"<span>{cat_0}</span>", result)
    self.assertIn(f"<span>{cat_1}</span>", result)
    # Check sorting
    i_0 = result.find(cat_0)
    i_1 = result.find(cat_1)
    self.assertLess(i_0, i_1)

    endpoint = "/h/transactions/options/tag"
    result, _ = self.web_get(endpoint)
    self.assertEqual(4, result.count("span"))
    self.assertIn("<span>[blank]</span>", result)
    self.assertIn(f"<span>{tag_1}</span>", result)
    # Check sorting
    i_blank = result.find("[blank]")
    i_0 = result.find(tag_1)
    self.assertLess(i_blank, i_1)

    endpoint = "/h/transactions/options/payee"
    result, _ = self.web_get(endpoint)
    self.assertEqual(6, result.count("span"))
    self.assertIn("<span>[blank]</span>", result)
    self.assertIn(f'value="{payee_0}"  hx-get', result)
    self.assertIn(f'value="{payee_1}"  hx-get', result)
    # Check sorting
    i_blank = result.find("[blank]")
    i_0 = result.find(payee_0)
    i_1 = result.find(payee_1)
    self.assertLess(i_blank, i_0)
    self.assertLess(i_0, i_1)

    queries = {"payee": payee_1}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(6, result.count("span"))
    self.assertIn("<span>[blank]</span>", result)
    self.assertIn(f'value="{payee_0}"  hx-get', result)
    self.assertIn(f'value="{payee_1}" checked hx-get', result)
    # Check sorting
    i_blank = result.find("[blank]")
    i_0 = result.find(payee_0)
    i_1 = result.find(payee_1)
    self.assertLess(i_blank, i_1)
    self.assertLess(i_1, i_0)

    queries = {"payee": [payee_0, payee_1], "search-payee": payee_0}
    result, _ = self.web_get(endpoint, queries=queries)
    self.assertEqual(2, result.count("span"))
    self.assertIn(f'value="{payee_0}" checked hx-get', result)

  def test_edit(self):
    p = self._portfolio
    today = datetime.date.today()
    d = self._setup_portfolio()

    t_0 = d["t_0"]
    t_split_0 = d["t_split_0"]
    payee_0 = d["payee_0"]
    cat_0 = d["cat_0"]
    cat_1 = d["cat_1"]

    endpoint = f"/h/transactions/t/{t_split_0}/edit"
    result, _ = self.web_get(endpoint)
    self.assertEqual(1, result.count('name="payee"'))

    endpoint = f"/h/transactions/t/{t_0}/edit"
    form = {"amount": ""}
    result, _ = self.web_post(endpoint, data=form)
    self.assertIn("Non-zero remaining amount to be assigned", result)

    form = {"amount": "100"}
    result, _ = self.web_post(endpoint, data=form)
    self.assertIn("Transaction must have at least one split", result)

    form = {"payee": "", "amount": "100"}
    result, _ = self.web_post(endpoint, data=form)
    self.assertIn("Transaction date must not be empty", result)

    form = {"date": today, "payee": "ab", "amount": "100"}
    result, _ = self.web_post(endpoint, data=form)
    self.assertIn("Transaction split payee must be at least 3 characters long",
                  result)

    # Add split
    new_date = today - datetime.timedelta(days=10)
    new_desc = self.random_string()
    form = {
        "date": new_date,
        "locked": "",
        "payee": [payee_0, ""],
        "description": [new_desc, ""],
        "category": [cat_0, cat_1],
        "tag": ["", ""],
        "amount": ["20", "80"],
    }
    result, headers = self.web_post(endpoint, data=form)
    self.assertEqual("update-transaction", headers["HX-Trigger"])

    with p.get_session() as s:
      categories = TransactionCategory.map_name(s)

      query = s.query(Transaction)
      query = query.where(Transaction.uuid == t_0)
      txn: Transaction = query.scalar()
      splits = txn.splits

      self.assertEqual(new_date, txn.date)
      self.assertTrue(txn.locked)
      self.assertEqual(2, len(splits))

      t_split = splits[0]
      self.assertEqual(new_date, t_split.date)
      self.assertTrue(t_split.locked)
      self.assertEqual(payee_0, t_split.payee)
      self.assertEqual(new_desc, t_split.description)
      self.assertEqual(cat_0, categories[t_split.category_id])
      self.assertIsNone(t_split.tag)
      self.assertEqual(20, t_split.amount)

      t_split = splits[1]
      self.assertEqual(new_date, t_split.date)
      self.assertTrue(t_split.locked)
      self.assertIsNone(t_split.payee)
      self.assertIsNone(t_split.description)
      self.assertEqual(cat_1, categories[t_split.category_id])
      self.assertIsNone(t_split.tag)
      self.assertEqual(80, t_split.amount)

    # Remove split
    new_date = today - datetime.timedelta(days=10)
    new_desc = self.random_string()
    form = {
        "date": new_date,
        "payee": payee_0,
        "description": new_desc,
        "category": cat_0,
        "tag": "",
        "amount": "100",
    }
    result, headers = self.web_post(endpoint, data=form)
    self.assertEqual("update-transaction", headers["HX-Trigger"])

    with p.get_session() as s:
      categories = TransactionCategory.map_name(s)

      query = s.query(Transaction)
      query = query.where(Transaction.uuid == t_0)
      txn: Transaction = query.scalar()
      splits = txn.splits

      self.assertEqual(new_date, txn.date)
      self.assertFalse(txn.locked)
      self.assertEqual(1, len(splits))

      t_split = splits[0]
      self.assertEqual(new_date, t_split.date)
      self.assertFalse(t_split.locked)
      self.assertEqual(payee_0, t_split.payee)
      self.assertEqual(new_desc, t_split.description)
      self.assertEqual(cat_0, categories[t_split.category_id])
      self.assertIsNone(t_split.tag)
      self.assertEqual(100, t_split.amount)

  def test_split(self):
    d = self._setup_portfolio()

    t_0 = d["t_0"]
    payee_0 = d["payee_0"]
    cat_0 = d["cat_0"]

    desc = self.random_string()
    tag = self.random_string()

    endpoint = f"/h/transactions/t/{t_0}/split"
    form = {
        "payee": payee_0,
        "description": desc,
        "category": cat_0,
        "tag": tag,
        "amount": "100",
    }
    result, _ = self.web_put(endpoint, data=form)
    self.assertEqual(2, result.count('name="payee"'))
    self.assertIn(f'name="payee" value="{payee_0}"', result)
    self.assertIn('name="payee" value=""', result)
    self.assertIn(f'name="description" value="{desc}"', result)
    self.assertIn('name="description" value=""', result)
    self.assertEqual(2, result.count("selected"))
    self.assertIn(f'value="{cat_0}" selected', result)
    self.assertIn('value="Uncategorized" selected', result)
    self.assertIn(f'name="tag" value="{tag}"', result)
    self.assertIn('name="tag" value=""', result)
    self.assertIn('name="amount" value="100.00"', result)
    self.assertIn('name="amount" value=""', result)

    form = {
        "payee": [payee_0, ""],
        "description": [desc, ""],
        "category": [cat_0, ""],
        "tag": [tag, ""],
        "amount": ["100", ""],
    }
    result, _ = self.web_delete(endpoint + "?index=2", data=form)
    self.assertEqual(1, result.count('name="payee"'))
    self.assertIn(f'name="payee" value="{payee_0}"', result)
    self.assertIn(f'name="description" value="{desc}"', result)
    self.assertEqual(1, result.count("selected"))
    self.assertIn(f'value="{cat_0}" selected', result)
    self.assertIn(f'name="tag" value="{tag}"', result)
    self.assertIn('name="amount" value="100.00"', result)
    self.assertIn('id="txn-remaining" hx-swap-oob="True"', result)

  def test_remaining(self):
    d = self._setup_portfolio()

    t_0 = d["t_0"]

    endpoint = f"/h/transactions/t/{t_0}/remaining"
    form = {"amount": "100"}
    result, _ = self.web_post(endpoint, data=form)
    self.assertIn(">$0.00</div>", result)

    form = {"amount": ["20", "20.001"]}
    result, _ = self.web_post(endpoint, data=form)
    self.assertIn(">$60.00</div>", result)
