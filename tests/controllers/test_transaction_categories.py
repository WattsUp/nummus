from __future__ import annotations

import datetime
import re

from nummus.models import (
    Account,
    AccountCategory,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from nummus.web_utils import HTTP_CODE_FORBIDDEN
from tests.controllers.base import WebTestBase


class TestTransactionCategory(WebTestBase):
    def setUp(self, **_) -> None:
        self.skipTest("Controller tests not updated yet")

    def test_overlay(self) -> None:
        p = self._portfolio
        self._setup_portfolio()

        with p.begin_session() as s:
            n = (
                s.query(TransactionCategory)
                .where(TransactionCategory.group != TransactionCategoryGroup.OTHER)
                .count()
            )

        endpoint = "transaction_categories.overlay"
        result, _ = self.web_get(endpoint)
        self.assertEqual(len(re.findall(r'<div id="category-[a-f0-9]{8}"', result)), n)
        self.assertIn("Edit transaction categories", result)

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
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Edit transaction categories", result)

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
        today = datetime.date.today()

        with p.begin_session() as s:
            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.name == "Other Income")
            t_cat = query.one()
            t_cat.emoji_name = 'Other Income"'
            t_cat_id = t_cat.id_
            t_cat_uri = t_cat.uri

        endpoint = "transaction_categories.category"
        url = endpoint, {"uri": t_cat_uri}
        result, _ = self.web_get(url)
        self.assertIn("Delete", result)
        self.assertIn('value="Other Income&#34;"', result)

        name = self.random_string()
        form = {"name": name + " 😀", "group": "transfer", "essential": True}
        result, _ = self.web_put(url, data=form)
        self.assertIn("Edit transaction categories", result)

        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id)
                .one()
            )
            self.assertEqual(t_cat.name, name)
            self.assertEqual(t_cat.emoji_name, name + " 😀")
            self.assertEqual(t_cat.group, TransactionCategoryGroup.TRANSFER)
            self.assertTrue(t_cat.essential)

        e_str = "Transaction category name must be at least 2 characters long"
        form = {"name": "a", "group": "other"}
        result, _ = self.web_put(url, data=form)
        self.assertIn(e_str, result)

        # Add transaction that needs to move
        with p.begin_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.flush()

            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))
            s.flush()

            t_split_id = t_split.id_

        result, _ = self.web_delete(url)
        self.assertIn("Edit transaction categories", result)

        with p.begin_session() as s:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.id_ == t_split_id)
            t_split: TransactionSplit = query.scalar()

            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.id_ == t_split.category_id)
            t_cat = query.scalar()

            self.assertEqual(t_cat.name, "Uncategorized")

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
            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.locked.is_(True))
            t_cat = query.first()
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
        result, _ = self.web_put(url, data=form)
        self.assertIn("Edit transaction categories", result)

        # Only can edit emoji for a locked category
        with p.begin_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id)
                .first()
            )
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            self.assertEqual(t_cat.name, "Dividends Received")
            self.assertEqual(t_cat.emoji_name, "😀 Dividends Received 😀")
            self.assertNotEqual(t_cat.group, TransactionCategoryGroup.TRANSFER)
