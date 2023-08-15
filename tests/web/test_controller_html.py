"""Test module nummus.web.controller_html
"""

import datetime
from decimal import Decimal
import re

from nummus import custom_types as t
from nummus.web import controller_html
from nummus.models import (Account, AccountCategory, Transaction,
                           TransactionSplit)

from tests.web.base import WebTestBase


class TestControllerHTML(WebTestBase):
  """Test controller_html methods
  """

  def _test_valid_html(self, s: str):
    """Test HTML is valid based on tags

    Args:
      s: String to test
    """
    tags: t.Strings = re.findall(r"<(/?\w+)(?: [^<>]+)?>", s)
    DOMTree = t.Dict[str, "DOMTree"]
    tree: DOMTree = {"__parent__": (None, None)}
    current_node = tree
    for tag in tags:
      if tag[0] == "/":
        # Close tag
        current_tag, parent = current_node.pop("__parent__")
        current_node = parent
        self.assertEqual(current_tag, tag[1:])
      elif tag in ["link", "meta", "path"]:
        # Tags without close tags
        current_node[tag] = {}
      else:
        current_node[tag] = {"__parent__": (tag, current_node)}
        current_node = current_node[tag]

    # Got back up to the root element
    tag, parent = current_node.pop("__parent__")
    self.assertEqual(tag, None)
    self.assertEqual(parent, None)

  def setUp(self):
    self._original_render_template = controller_html.flask.render_template

    self._called_context: t.DictAny = {}

    def render_template(path: str, **context: t.DictAny) -> str:
      self._called_context.clear()
      self._called_context.update(**context)
      return self._original_render_template(path, **context)

    controller_html.flask.render_template = render_template

    return super().setUp()

  def tearDown(self):
    controller_html.flask.render_template = self._original_render_template
    return super().tearDown()

  def test_get_home(self):
    endpoint = "/"
    result, _ = self.api_get(endpoint, content_type="text/html; charset=utf-8")
    target = '<!DOCTYPE html>\n<html lang="en">'
    self.assertEqual(target, result[:len(target)])
    target = "</html>"
    self.assertEqual(target, result[-len(target):])
    self._test_valid_html(result)

  def test_get_sidebar(self):
    p = self._portfolio

    today = datetime.date.today()

    endpoint = "/sidebar"
    result, _ = self.api_get(endpoint, content_type="text/html; charset=utf-8")
    # Can't easily test if HTML is actually as desired
    # Just test HTML is valid and context was as expected
    self._test_valid_html(result)

    target = {
        "net-worth": Decimal(0),
        "assets": Decimal(0),
        "liabilities": Decimal(0),
        "assets-w": 0,
        "liabilities-w": 0,
        "categories": {}
    }
    self.assertDictEqual({"context": target}, self._called_context)

    with p.get_session() as s:
      acct_checking = Account(name="Monkey Bank Checking",
                              institution="Monkey Bank",
                              category=AccountCategory.CASH)
      acct_savings = Account(name="Monkey Bank Savings",
                             institution="Monkey Bank",
                             category=AccountCategory.CASH)
      s.add_all((acct_checking, acct_savings))
      s.commit()

      txn = Transaction(account=acct_savings,
                        date=today,
                        total=100,
                        statement=self.random_string())
      t_split = TransactionSplit(total=txn.total, parent=txn)
      s.add_all((txn, t_split))

      txn = Transaction(account=acct_checking,
                        date=today,
                        total=-50,
                        statement=self.random_string())
      t_split = TransactionSplit(total=txn.total, parent=txn)
      s.add_all((txn, t_split))

      s.commit()

    result, _ = self.api_get(endpoint, content_type="text/html; charset=utf-8")
    self._test_valid_html(result)

    target_accounts = [{
        "institution": "Monkey Bank",
        "name": "Monkey Bank Checking",
        "updated_days_ago": 0,
        "value": Decimal("-50.000000")
    }, {
        "institution": "Monkey Bank",
        "name": "Monkey Bank Savings",
        "updated_days_ago": 0,
        "value": Decimal("100.000000")
    }]
    target = {
        "net-worth": Decimal("50.000000"),
        "assets": Decimal("100.000000"),
        "liabilities": Decimal("-50.000000"),
        "assets-w": Decimal("66.67"),
        "liabilities-w": Decimal("33.33"),
        "categories": {
            AccountCategory.CASH: (Decimal("50.000000"), target_accounts)
        }
    }
    self.assertDictEqual({"context": target}, self._called_context)
