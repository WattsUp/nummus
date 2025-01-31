from __future__ import annotations

import datetime
import re
from decimal import Decimal

from nummus.controllers import accounts
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from nummus.web_utils import HTTP_CODE_BAD_REQUEST
from tests.controllers.base import WebTestBase


class TestAccount(WebTestBase):
    def test_account(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        cat_1 = d["cat_1"]

        endpoint = "accounts.account"
        url = endpoint, {"uri": acct_uri}
        result, _ = self.web_get(url)
        self.assertNotIn("<html", result)
        self.assertIn("Edit account", result)

        name = self.random_string()
        institution = self.random_string()
        form = {
            "institution": institution,
            "name": name,
            "category": "credit",
            "number": "",
        }
        result, headers = self.web_put(url, data=form)
        self.assertIn("HX-Trigger", headers, msg=f"Response lack HX-Trigger {result}")
        self.assertEqual(headers["HX-Trigger"], "update-account")
        self.assertNotIn("<svg", result)  # No error SVG
        with p.begin_session() as s:
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
            "number": "",
            "closed": "",
        }
        result, _ = self.web_put(url, data=form)
        e_str = "Cannot close Account with non-zero balance"
        self.assertIn(e_str, result)
        with p.begin_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertFalse(acct.closed)

        form = {
            "institution": institution,
            "name": "a",
            "category": "credit",
            "number": "",
        }
        result, _ = self.web_put(url, data=form)
        e_str = "Account name must be at least 2 characters long"
        self.assertIn(e_str, result)
        with p.begin_session() as s:
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
        result, _ = self.web_put(url, data=form)
        e_str = "Account category must not be None"
        self.assertIn(e_str, result)

        # Cancel balance
        with p.begin_session() as s:
            today = datetime.date.today()

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")

            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=-90,
                statement=self.random_string(),
                locked=True,
                linked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                category_id=categories[cat_1],
            )
            s.add_all((txn, t_split))

        form = {
            "institution": institution,
            "name": name,
            "category": "credit",
            "number": "",
            "closed": "",
        }
        result, _ = self.web_put(url, data=form)
        self.assertNotIn("<svg", result)  # No error SVG
        with p.begin_session() as s:
            acct = s.query(Account).first()
            if acct is None:
                self.fail("Account is missing")
            self.assertTrue(acct.closed)

    def test_page(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]

        endpoint = "accounts.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri}),
            headers=headers,
        )
        self.assertRegex(result, r"<h1.*>\$90.00</h1>")
        self.assertRegex(result, r"<script>accounts\.update\(.*\)</script>")
        self.assertRegex(result, r"<div.*>Uncategorized</div>")
        self.assertRegex(result, r"<div.*>\$100.00</div>")
        self.assertRegex(result, r"<div.*>-\$10.00</div>")
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}"')
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}"')

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "last-year"}),
            headers=headers,
        )
        self.assertRegex(result, r"<h1.*>\$90.00</h1>")
        self.assertRegex(result, r"<script>accounts\.update\(.*\)</script>")
        self.assertNotRegex(result, r"<div.*>Uncategorized</div>")
        self.assertNotRegex(result, r"<div.*>\$100.00</div>")
        self.assertNotRegex(result, r"<div.*>-\$10.00</div>")
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}"')

    def test_txns(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        acct_uri = d["acct_uri"]
        a_uri_0 = d["a_uri_0"]
        a_uri_1 = d["a_uri_1"]
        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]

        accounts.PREVIOUS_PERIOD["start"] = None
        accounts.PREVIOUS_PERIOD["end"] = None

        endpoint = "accounts.txns"
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "all"}),
        )
        self.assertNotIn("<html", result)
        # First different call for table should update chart as well
        self.assertRegex(
            result,
            r'<script>accounts\.update\(.*"min": null.*\)</script>',
        )
        m = re.search(
            r'<script>accounts\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
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
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}"')
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}"')
        self.assertNotIn('id="assets"', result)  # Not an investment account

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "all"}),
        )
        # Second call for table should not update chart as well
        self.assertNotRegex(result, r"<script>accounts\.update\(.*\)</script>")

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "30-days"}),
        )
        self.assertRegex(
            result,
            r'<script>accounts\.update\(.*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "last-year"}),
        )
        self.assertRegex(
            result,
            r'<script>accounts\.update\(.*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "months"', result)
        self.assertNotRegex(result, r"<div .*>Uncategorized</div>")
        self.assertNotRegex(result, r"<div .*>\$100.00</div>")
        self.assertNotRegex(result, r"<div .*>-\$10.00</div>")
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}"')

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "5-years"}),
        )
        self.assertRegex(
            result,
            r'<script>accounts\.update\(.*"min": \[.+\].*\)</script>',
        )
        m = re.search(
            r'<script>accounts\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
        self.assertIn('"date_mode": "years"', result)

        # Add an asset transaction
        with p.begin_session() as s:
            acct_id = Account.uri_to_id(acct_uri)
            a_id_1 = Asset.uri_to_id(a_uri_1)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            # Buy the house but no ticker so excluded
            txn = Transaction(
                account_id=acct_id,
                date=today - datetime.timedelta(days=2),
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_1,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))

        headers = {"HX-Trigger": "txn-table"}
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "all"}),
            headers=headers,
        )
        # Get the asset block
        m = re.search(r'id="assets"(.*)', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="assets-total"')

        self.assertIn(f'id="asset-{a_uri_1}"', result_assets)
        self.assertRegex(
            result_assets,
            r"(Real Estate).*(Fruit Ct\. House).*"
            r"(1\.000000).*(\$0\.00).*(0\.00%).*(-\$10\.00)[^0-9]*",
        )
        self.assertNotIn(f'id="asset-{a_uri_0}"', result_assets)
        self.assertRegex(result_total, r"(Total).*(\$80\.00).*(-\$10\.00)[^0-9]*")

        # Add a valuation for the house with zero profit
        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=a_id_1,
                date_ord=today_ord - 2,
                value=10,
            )
            s.add(v)

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "all"}),
            headers=headers,
        )
        # Get the asset block
        m = re.search(r'id="assets"(.*)', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="assets-total"')

        self.assertIn(f'id="asset-{a_uri_1}"', result_assets)
        self.assertRegex(
            result_assets,
            r"(Real Estate).*(Fruit Ct\. House).*"
            r"(1\.000000).*(\$10\.00).*(11\.11%).*(\$0\.00)[^0-9]*",
        )
        self.assertNotIn(f'id="asset-{a_uri_0}"', result_assets)
        self.assertRegex(result_total, r"(Total).*(\$90\.00).*(\$0\.00)[^0-9]*")

        # Sell house for $20
        with p.begin_session() as s:
            acct_id = Account.uri_to_id(acct_uri)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date=today - datetime.timedelta(days=1),
                amount=20,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_1,
                asset_quantity_unadjusted=-1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))

        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, **queries}),
            headers=headers,
        )
        # Get the asset block
        m = re.search(r'id="assets"(.*)', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="assets-total"')

        self.assertNotIn(f'id="asset-{a_uri_0}"', result_assets)
        self.assertNotIn(f'id="asset-{a_uri_1}"', result_assets)
        self.assertRegex(result_total, r"(Total).*(\$100\.00).*(\$0\.00)[^0-9]*")

    def test_txns_options(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        d["payee_0"]
        d["payee_1"]
        d["t_split_0"]
        d["t_split_1"]
        cat_0 = d["cat_0"]
        cat_1 = d["cat_1"]
        tag_1 = d["tag_1"]

        endpoint = "accounts.txns_options"
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "field": "account"}),
            rc=HTTP_CODE_BAD_REQUEST,
        )

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "field": "category", "period": "all"}),
        )
        self.assertNotIn("<html", result)
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_0, i_1)

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "field": "category", "category": cat_1}),
        )
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{cat_1}"[ \n]+checked[ \n]+hx-get')
        # Check sorting
        i_0 = result.find(cat_0)
        i_1 = result.find(cat_1)
        self.assertLess(i_1, i_0)

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "field": "tag"}),
        )
        self.assertEqual(result.count("span"), 4)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertRegex(result, rf'value="{tag_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        # Check sorting
        i_blank = result.find("[blank]")
        i_1 = result.find(tag_1)
        self.assertLess(i_blank, i_1)

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "field": "unknown"}),
            rc=HTTP_CODE_BAD_REQUEST,
        )

    def test_new_txn(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()

        acct = d["acct"]
        acct_uri = d["acct_uri"]

        endpoint = "accounts.new_txn"
        result, _ = self.web_get((endpoint, {"uri": acct_uri}))
        self.assertIn("New transaction", result)
        self.assertIn(f"selected>{acct}", result)

        form = {}
        result, _ = self.web_post((endpoint, {"uri": acct_uri}), data=form)
        self.assertIn("Transaction date must not be empty", result)

        form = {"date": today}
        result, _ = self.web_post((endpoint, {"uri": acct_uri}), data=form)
        self.assertIn("Transaction amount must not be empty", result)

        form = {"date": today, "amount": "1000"}
        result, _ = self.web_post((endpoint, {"uri": acct_uri}), data=form)
        self.assertIn("Transaction account must not be empty", result)

        form = {"date": today, "amount": "1000", "account": acct}
        result, _ = self.web_post((endpoint, {"uri": acct_uri}), data=form)
        # Redirect to edit after creating
        self.assertIn("Edit transaction", result)
        with p.begin_session() as s:
            acct_id = Account.uri_to_id(acct_uri)
            txn = (
                s.query(Transaction)
                .where(
                    Transaction.account_id == acct_id,
                    Transaction.amount == Decimal("1000"),
                )
                .one()
            )
            self.assertEqual(txn.statement, "Manually added")
            self.assertFalse(txn.locked, "Transaction unexpectably locked")
            self.assertFalse(txn.linked, "Transaction unexpectably linked")

            category_id = (
                s.query(TransactionCategory.id_)
                .where(TransactionCategory.name == "Uncategorized")
                .scalar()
            )
            t_split = (
                s.query(TransactionSplit)
                .where(
                    TransactionSplit.account_id == acct_id,
                    TransactionSplit.amount == Decimal("1000"),
                )
                .one()
            )
            self.assertEqual(t_split.category_id, category_id)
