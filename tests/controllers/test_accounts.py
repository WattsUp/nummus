from __future__ import annotations

from nummus.controllers import accounts
from nummus.models import Account, AccountCategory
from tests.controllers.base import HTTP_CODE_BAD_REQUEST, WebTestBase


class TestAccount(WebTestBase):
    def test_edit(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]

        endpoint = f"/h/accounts/a/{acct_uri}/edit"
        result, _ = self.web_get(endpoint)
        self.assertIn("Edit account", result)

        name = self.random_string()
        institution = self.random_string()
        form = {"institution": institution, "name": name, "category": "credit"}
        result, headers = self.web_post(endpoint, data=form)
        self.assertEqual(headers["HX-Trigger"], "update-account")
        with p.get_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertEqual(acct.name, name)
            self.assertEqual(acct.institution, institution)
            self.assertEqual(acct.category, AccountCategory.CREDIT)
            self.assertFalse(acct.closed)

        form = {
            "institution": institution,
            "name": name,
            "category": "credit",
            "closed": "",
        }
        result, _ = self.web_post(endpoint, data=form)
        e_str = "Cannot close Account with non-zero balance"
        self.assertIn(e_str, result)
        with p.get_session() as s:
            self.assertFalse(acct.closed)

        form = {
            "institution": institution,
            "name": "ab",
            "category": "credit",
        }
        result, _ = self.web_post(endpoint, data=form)
        e_str = "Account name must be at least 3 characters long"
        self.assertIn(e_str, result)
        with p.get_session() as s:
            self.assertFalse(acct.closed)

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

        acct_uri = d["acct_uri"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]

        accounts.PREVIOUS_PERIOD["start"] = None
        accounts.PREVIOUS_PERIOD["end"] = None

        endpoint = f"/h/accounts/a/{acct_uri}/table"
        result, _ = self.web_get(endpoint)
        # First different call for table should update chart as well
        self.assertRegex(result, r"<script>accountChart\.update\(.*\)</script>")
        self.assertNotIn("txn-account", result)  # No account column on account page
        self.assertRegex(result, r"<div .*>Uncategorized</div>")
        self.assertRegex(result, r"<div .*>\$100.00</div>")
        self.assertRegex(result, r"<div .*>-\$10.00</div>")
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

        result, _ = self.web_get(endpoint)
        # Second call for table should not update chart as well
        self.assertNotRegex(result, r"<script>accountChart\.update\(.*\)</script>")

        queries = {"period": "last-year"}
        result, _ = self.web_get(endpoint, queries)
        self.assertNotRegex(result, r"<div .*>Uncategorized</div>")
        self.assertNotRegex(result, r"<div .*>\$100.00</div>")
        self.assertNotRegex(result, r"<div .*>-\$10.00</div>")
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

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
