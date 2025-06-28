from __future__ import annotations

import datetime
import re
from decimal import Decimal

from nummus.models import (
    Account,
    AccountCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestAccount(WebTestBase):

    def test_page_all(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        acct_name = d["acct_name"]

        endpoint = "accounts.page_all"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            endpoint,
            headers=headers,
        )
        self.assertIn("Accounts", result)
        self.assertIn("Cash", result)
        self.assertNotIn("Investment", result)
        self.assertIn(acct_uri, result)
        self.assertIn(acct_name, result)
        matches = re.findall(r"(-?\$\d+)<", result)
        self.assertEqual(matches, ["$90", "$90", "$0"])
        self.assertIn("2 transactions today", result)

        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            # Zero out account
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=-90,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["groceries"],
            )
            s.add_all((txn, t_split))
            # And close
            s.query(Account).where(Account.id_ == acct_id).update(
                {Account.closed: True},
            )

        result, _ = self.web_get(
            endpoint,
            headers=headers,
        )
        self.assertIn("Accounts", result)
        self.assertNotIn("Cash", result)
        self.assertNotIn("Investment", result)
        self.assertNotIn(acct_uri, result)
        self.assertNotIn(acct_name, result)
        matches = re.findall(r"(-?\$\d+)<", result)
        self.assertEqual(matches, ["$0", "$0", "$0"])

        result, _ = self.web_get(
            (endpoint, {"include-closed": True}),
            headers=headers,
        )
        self.assertIn("Accounts", result)
        self.assertIn("Cash", result)
        self.assertNotIn("Investment", result)
        self.assertIn(acct_uri, result)
        self.assertIn(acct_name, result)
        matches = re.findall(r"(-?\$\d+)<", result)
        self.assertEqual(matches, ["$0", "$0", "$0"])

        with p.begin_session() as s:
            # Reopen
            s.query(Account).where(Account.id_ == acct_id).update(
                {Account.closed: False},
            )
            # Add future transaction
            txn = Transaction(
                account_id=acct_id,
                date=today + datetime.timedelta(days=1),
                amount=-90,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories["groceries"],
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Accounts", result)
        self.assertIn("Cash", result)
        self.assertNotIn("Investment", result)
        self.assertIn(acct_uri, result)
        self.assertIn(acct_name, result)
        matches = re.findall(r"(-?\$\d+)<", result)
        # Net worth does not include future
        self.assertEqual(matches, ["$0", "$0", "$0"])
        self.assertIn("1 future transaction pending", result)

    def test_page(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        txn_0_uri = d["txn_0_uri"]
        txn_1_uri = d["txn_1_uri"]
        asset_0_id = d["asset_0_id"]

        endpoint = "accounts.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri}),
            headers=headers,
        )
        self.assertNotIn("Performance", result)
        self.assertIn(rf'hx-get="/h/transactions/t/{txn_0_uri}"', result)
        self.assertIn(rf'hx-get="/h/transactions/t/{txn_1_uri}"', result)

        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            s.query(Account).where(Account.id_ == acct_id).update(
                {Account.category: AccountCategory.INVESTMENT},
            )
            txn = Transaction(
                account_id=acct_id,
                date=today - datetime.timedelta(days=1),
                amount=0,
                statement=self.random_string(),
            )
            t_split_0 = TransactionSplit(
                amount=10,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=0,
                category_id=categories["dividends received"],
            )
            t_split_1 = TransactionSplit(
                amount=-10,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=Decimal("0.1"),
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split_0, t_split_1))

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=0,
                statement=self.random_string(),
            )
            t_split_0 = TransactionSplit(
                amount=-1,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=0,
                category_id=categories["investment fees"],
            )
            t_split_1 = TransactionSplit(
                amount=1,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=Decimal("-0.1"),
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split_0, t_split_1))

        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "period": "2000"}),
            headers=headers,
        )
        self.assertIn("Performance", result)
        self.assertNotIn(rf'hx-get="/h/transactions/t/{txn_0_uri}"', result)
        self.assertNotIn(rf'hx-get="/h/transactions/t/{txn_1_uri}"', result)
        self.assertIn("$10.00", result)
        self.assertIn("-$1.00", result)

    def test_account(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.datetime.now().astimezone().date()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        cat_1_id = d["cat_1_id"]

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
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "account")
        with p.begin_session() as s:
            acct = s.query(Account).where(Account.id_ == acct_id).one()
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
                payee=self.random_string(),
                cleared=True,
            )
            t_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=cat_1_id,
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

    def test_performance(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        asset_0_id = d["asset_0_id"]

        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            s.query(Account).where(Account.id_ == acct_id).update(
                {Account.category: AccountCategory.INVESTMENT},
            )
            txn = Transaction(
                account_id=acct_id,
                date=today - datetime.timedelta(days=1),
                amount=0,
                statement=self.random_string(),
            )
            t_split_0 = TransactionSplit(
                amount=10,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=0,
                category_id=categories["dividends received"],
            )
            t_split_1 = TransactionSplit(
                amount=-10,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=Decimal("0.1"),
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split_0, t_split_1))

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=0,
                statement=self.random_string(),
            )
            t_split_0 = TransactionSplit(
                amount=-1,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=0,
                category_id=categories["investment fees"],
            )
            t_split_1 = TransactionSplit(
                amount=1,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=Decimal("-0.1"),
                category_id=categories["securities traded"],
            )
            s.add_all((txn, t_split_0, t_split_1))

        endpoint = "accounts.performance"
        result, _ = self.web_get((endpoint, {"uri": acct_uri}))
        self.assertIn("Performance", result)
        self.assertIn("$10.00", result)
        self.assertIn("-$1.00", result)

    def test_validation(self) -> None:
        d = self._setup_portfolio()

        acct_id = d["acct_id"]
        acct_uri = d["acct_uri"]
        acct_name = d["acct_name"]

        endpoint = "accounts.validation"

        result, _ = self.web_get((endpoint, {"uri": acct_uri, "name": " "}))
        self.assertEqual("Required", result)

        result, _ = self.web_get((endpoint, {"uri": acct_uri, "name": "a"}))
        self.assertEqual("2 characters required", result)

        result, _ = self.web_get((endpoint, {"uri": acct_uri, "name": "ab"}))
        self.assertEqual("", result)

        # Number not required
        result, _ = self.web_get((endpoint, {"uri": acct_uri, "number": " "}))
        self.assertEqual("", result)

        acct_uri = Account.id_to_uri(acct_id + 1)

        # Name cannot be duplicated
        result, _ = self.web_get((endpoint, {"uri": acct_uri, "name": acct_name}))
        self.assertEqual("Must be unique", result)

        # Institution not checked for duplication
        result, _ = self.web_get(
            (endpoint, {"uri": acct_uri, "institution": "Monkey Bank"}),
        )
        self.assertEqual("", result)

    def test_txns(self) -> None:
        d = self._setup_portfolio()
        today = datetime.datetime.now().astimezone().date()

        acct_name = d["acct_name"]
        acct_uri = d["acct_uri"]
        txn_0_uri = d["txn_0_uri"]
        txn_1_uri = d["txn_1_uri"]

        endpoint = "accounts.txns"
        result, headers = self.web_get(
            (endpoint, {"uri": acct_uri}),
        )
        self.assertEqual(headers.get("HX-Push-Url"), f"/accounts/{acct_uri}")
        self.assertIn(txn_0_uri, result)
        self.assertIn(txn_1_uri, result)
        self.assertIn(
            f"<title>Account {acct_name} - nummus</title>",
            result,
        )

        result, headers = self.web_get(
            (endpoint, {"uri": acct_uri, "page": today.isoformat(), "period": "all"}),
        )
        self.assertNotIn("HX-Push-Url", headers)
        self.assertEqual(result.count('<div class="txn"'), 2)
        self.assertIn(txn_0_uri, result)
        self.assertIn(txn_1_uri, result)
        self.assertIn(
            f"<title>Account {acct_name}, All Transactions - nummus</title>",
            result,
        )

    def test_txns_options(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]
        acct_name = d["acct_name"]
        cat_0_uri = d["cat_0_uri"]
        cat_0_emoji_name = d["cat_0_emoji_name"]
        cat_1_uri = d["cat_1_uri"]
        cat_1_emoji_name = d["cat_1_emoji_name"]

        endpoint = "accounts.txns_options"
        result, _ = self.web_get((endpoint, {"uri": acct_uri}))
        self.assertNotIn(acct_name, result)
        self.assertIn(cat_0_uri, result)
        self.assertIn(cat_0_emoji_name, result)
        self.assertIn(cat_1_uri, result)
        self.assertIn(cat_1_emoji_name, result)
        self.assertNotIn("checked", result)
