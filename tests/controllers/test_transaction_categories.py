from __future__ import annotations

import datetime

from nummus.models import (
    Account,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from nummus.web_utils import HTTP_CODE_FORBIDDEN
from tests.controllers.base import WebTestBase


class TestTransactionCategory(WebTestBase):

    def test_page(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "other income")
                .one()
            )
            t_cat_uri = t_cat.uri

        endpoint = "transaction_categories.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertRegex(result, rf'hx-get="/h/txn-categories/c/{t_cat_uri}"')

    def test_new(self) -> None:
        p = self._portfolio
        self._setup_portfolio()

        with p.begin_session() as s:
            n_before = s.query(TransactionCategory).count()

        endpoint = "transaction_categories.new"
        result, _ = self.web_get(endpoint)
        self.assertNotIn("Delete", result)

        name = self.random_string()
        form = {"name": name, "group": "expense", "essential": True}
        result, headers = self.web_post(endpoint, data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "category")

        with p.begin_session() as s:
            n_after = s.query(TransactionCategory).count()
            self.assertEqual(n_after, n_before + 1)

        e_str = "Transaction category name must be unique"
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(e_str, result)

        with p.begin_session() as s:
            n_after = s.query(TransactionCategory).count()
            self.assertEqual(n_after, n_before + 1)

    def test_category(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        acct_uri = d["acct_uri"]
        acct_id = Account.uri_to_id(acct_uri)

        today = datetime.date.today()

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "other income")
                .one()
            )
            t_cat.emoji_name = 'Other Income"'
            t_cat_id = t_cat.id_
            t_cat_uri = t_cat.uri

        endpoint = "transaction_categories.category"
        url = endpoint, {"uri": t_cat_uri}
        result, _ = self.web_get(url)
        self.assertIn("Delete", result)
        self.assertIn(f"/c/{t_cat_uri}", result)

        name = self.random_string()
        form = {"name": name + " 😀", "group": "transfer", "essential": True}
        result, headers = self.web_put(url, data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "category")

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id)
                .one()
            )
            self.assertEqual(t_cat.name, name.lower())
            self.assertEqual(t_cat.emoji_name, name + " 😀")
            self.assertEqual(t_cat.group, TransactionCategoryGroup.TRANSFER)
            self.assertTrue(t_cat.essential)

        e_str = "Transaction category name must be at least 2 characters long"
        form = {"name": "a", "group": "other"}
        result, _ = self.web_put(url, data=form)
        self.assertIn(e_str, result)

        # Add transaction that needs to move
        with p.begin_session() as s:
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))
            s.flush()

            t_split_id = t_split.id_

        result, headers = self.web_delete(url)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "category")

        with p.begin_session() as s:
            t_split = (
                s.query(TransactionSplit)
                .where(TransactionSplit.id_ == t_split_id)
                .one()
            )
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_split.category_id)
                .one()
            )
            self.assertEqual(t_cat.name, "uncategorized")

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.locked.is_(True))
                .first()
            )
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            t_cat_uri = t_cat.uri

        url = endpoint, {"uri": t_cat_uri}
        self.web_delete(url, rc=HTTP_CODE_FORBIDDEN)

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.locked.is_(True))
                .first()
            )
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            t_cat_id = t_cat.id_
            t_cat_uri = t_cat.uri

        url = endpoint, {"uri": t_cat_uri}
        form = {"name": "😀", "group": "other"}
        result, _ = self.web_put(url, data=form)
        self.assertIn("Can only add/remove emojis on locked category", result)

        url = endpoint, {"uri": t_cat_uri}
        form = {"name": "😀 Dividends Received 😀", "group": "other"}
        result, headers = self.web_put(url, data=form)
        self.assertIn("snackbar-script", result)
        self.assertEqual(headers.get("HX-Trigger"), "category")

        # Only can edit emoji for a locked category
        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id)
                .one()
            )
            self.assertEqual(t_cat.name, "dividends received")
            self.assertEqual(t_cat.emoji_name, "😀 Dividends Received 😀")
            self.assertNotEqual(t_cat.group, TransactionCategoryGroup.TRANSFER)

    def test_validation(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "other income")
                .one()
            )
            t_cat_uri = t_cat.uri

        endpoint = "transaction_categories.validation"
        url = endpoint, {"uri": t_cat_uri, "name": "😀"}
        result, _ = self.web_get(url)
        self.assertEqual(result, "Required")

        url = endpoint, {"uri": t_cat_uri, "name": "😀 A"}
        result, _ = self.web_get(url)
        self.assertEqual(result, "2 characters required")

        url = endpoint, {"uri": t_cat_uri, "name": "Groceries"}
        result, _ = self.web_get(url)
        self.assertEqual(result, "Must be unique")

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.name == "transfers")
                .one()
            )
            t_cat_uri = t_cat.uri

        url = endpoint, {"uri": t_cat_uri, "name": "Transfer"}
        result, _ = self.web_get(url)
        self.assertEqual(result, "May only add/remove emojis")

        url = endpoint, {"uri": t_cat_uri, "name": "Transfers 😀"}
        result, _ = self.web_get(url)
        self.assertEqual(result, "")
