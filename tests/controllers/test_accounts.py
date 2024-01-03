from __future__ import annotations

import datetime
import re

from nummus.controllers import accounts
from nummus.models import (
    Account,
    AccountCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import HTTP_CODE_BAD_REQUEST, WebTestBase


class TestAccount(WebTestBase):
    def test_edit(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        cat_1 = d["cat_1"]

        endpoint = f"/h/accounts/a/{acct_uri}/edit"
        result, _ = self.web_get(endpoint)
        self.assertIn("Edit account", result)

        name = self.random_string()
        institution = self.random_string()
        form = {
            "institution": institution,
            "name": name,
            "category": "credit",
            "number": "",
            "emergency": "",
        }
        result, headers = self.web_post(endpoint, data=form)
        self.assertEqual(headers["HX-Trigger"], "update-account")
        self.assertNotIn("<svg", result)  # No error SVG
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertEqual(acct.name, name)
            self.assertEqual(acct.institution, institution)
            self.assertEqual(acct.category, AccountCategory.CREDIT)
            self.assertFalse(acct.closed)
            self.assertTrue(acct.emergency)

        form = {
            "institution": institution,
            "name": name,
            "category": "credit",
            "number": "",
            "closed": "",
        }
        result, _ = self.web_post(endpoint, data=form)
        e_str = "Cannot close Account with non-zero balance"
        self.assertIn(e_str, result)
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertFalse(acct.closed)

        form = {
            "institution": institution,
            "name": "ab",
            "category": "credit",
            "number": "",
        }
        result, _ = self.web_post(endpoint, data=form)
        e_str = "Account name must be at least 3 characters long"
        self.assertIn(e_str, result)
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertFalse(acct.closed)

        form = {
            "institution": institution,
            "name": "ab",
            "category": "",
            "number": "",
        }
        result, _ = self.web_post(endpoint, data=form)
        e_str = "Account category must not be None"
        self.assertIn(e_str, result)

        # Cancel balance
        with p.get_session() as s:
            today = datetime.date.today()
            today_ord = today.toordinal()

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")

            txn = Transaction(
                account_id=acct.id_,
                date_ord=today_ord,
                amount=-90,
                statement=self.random_string(),
                locked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                category_id=categories[cat_1],
            )
            s.add_all((txn, t_split))
            s.commit()

        form = {
            "institution": institution,
            "name": name,
            "category": "credit",
            "number": "",
            "closed": "",
        }
        result, _ = self.web_post(endpoint, data=form)
        self.assertNotIn("<svg", result)  # No error SVG
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertTrue(acct.closed)
            self.assertFalse(acct.emergency)

    def test_page(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]

        endpoint = f"/accounts/{acct_uri}"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Today's Balance <b>$90.00</b>", result)
        self.assertRegex(result, r"<script>accountChart\.update\(.*\)</script>")
        self.assertRegex(result, r"<div .*>Uncategorized</div>")
        self.assertRegex(result, r"<div .*>\$100.00</div>")
        self.assertRegex(result, r"<div .*>-\$10.00</div>")
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

        queries = {"period": "last-year"}
        result, _ = self.web_get(endpoint, queries, headers=headers)
        self.assertIn("Today's Balance <b>$90.00</b>", result)
        self.assertRegex(result, r"<script>accountChart\.update\(.*\)</script>")
        self.assertNotRegex(result, r"<div .*>Uncategorized</div>")
        self.assertNotRegex(result, r"<div .*>\$100.00</div>")
        self.assertNotRegex(result, r"<div .*>-\$10.00</div>")
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

    def test_table(self) -> None:
        d = self._setup_portfolio()
        today = datetime.date.today()

        acct_uri = d["acct_uri"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]

        accounts.PREVIOUS_PERIOD["start"] = None
        accounts.PREVIOUS_PERIOD["end"] = None

        endpoint = f"/h/accounts/a/{acct_uri}/table"
        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries)
        # First different call for table should update chart as well
        self.assertRegex(
            result,
            r'<script>accountChart\.update\(.*"min": null.*\)</script>',
        )
        m = re.search(
            r'<script>accountChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertIn(today.isoformat(), dates_s)
        self.assertIn('"date_mode": "days"', result)
        self.assertNotIn("txn-account", result)  # No account column on account page
        self.assertRegex(result, r"<div .*>Uncategorized</div>")
        self.assertRegex(result, r"<div .*>\$100.00</div>")
        self.assertRegex(result, r"<div .*>-\$10.00</div>")
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

        result, _ = self.web_get(endpoint, queries)
        # Second call for table should not update chart as well
        self.assertNotRegex(result, r"<script>accountChart\.update\(.*\)</script>")

        queries = {"period": "30-days"}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r'<script>accountChart\.update\(.*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)

        queries = {"period": "last-year"}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r'<script>accountChart\.update\(.*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "months"', result)
        self.assertNotRegex(result, r"<div .*>Uncategorized</div>")
        self.assertNotRegex(result, r"<div .*>\$100.00</div>")
        self.assertNotRegex(result, r"<div .*>-\$10.00</div>")
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

        queries = {"period": "5-years"}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r'<script>accountChart\.update\(.*"min": \[.+\].*\)</script>',
        )
        m = re.search(
            r'<script>accountChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
        self.assertIn('"date_mode": "years"', result)

    def test_options(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        d["payee_0"]
        d["payee_1"]
        d["t_split_0"]
        d["t_split_1"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]
        tag_1 = d["tag_1"]

        endpoint = f"/h/accounts/a/{acct_uri}/options/account"
        self.web_get(endpoint, rc=HTTP_CODE_BAD_REQUEST)

        endpoint = f"/h/accounts/a/{acct_uri}/options/category"
        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_0, i_1)

        queries = {"category": cat_1}
        result, _ = self.web_get(endpoint, queries=queries)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+checked[ \n]+hx-get')
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_1, i_0)

        endpoint = f"/h/accounts/a/{acct_uri}/options/tag"
        result, _ = self.web_get(endpoint)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{tag_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_blank = result.find("[blank]")
        i_0 = result.find(tag_1)
        self.assertLess(i_blank, i_1)
