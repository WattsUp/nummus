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
from tests.controllers.base import WebTestBase


class TestTransactionCategory(WebTestBase):
    def test_overlay(self) -> None:
        p = self._portfolio

        with p.get_session() as s:
            n = s.query(TransactionCategory).count()

        endpoint = "/h/txn-categories"
        result, _ = self.web_get(endpoint)
        self.assertEqual(len(re.findall(r'<div id="category-[a-f0-9]{8}"', result)), n)
        self.assertIn("Edit transaction categories", result)

    def test_new(self) -> None:
        p = self._portfolio

        with p.get_session() as s:
            n_before = s.query(TransactionCategory).count()

        endpoint = "/h/txn-categories/new"
        result, _ = self.web_get(endpoint)
        self.assertNotIn("Delete", result)

        name = self.random_string()
        form = {"name": name, "group": "other"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Edit transaction categories", result)

        with p.get_session() as s:
            n_after = s.query(TransactionCategory).count()
            self.assertEqual(n_after, n_before + 1)

        e_str = "Transaction category name must be unique"
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(e_str, result)

        with p.get_session() as s:
            n_after = s.query(TransactionCategory).count()
            self.assertEqual(n_after, n_before + 1)

    def test_edit(self) -> None:
        p = self._portfolio

        with p.get_session() as s:
            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.locked.is_(False))
            t_cat = query.first()
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            t_cat_id = t_cat.id_
            t_cat_uri = t_cat.uri

        endpoint = f"/h/txn-categories/c/{t_cat_uri}/edit"
        result, _ = self.web_get(endpoint)
        self.assertIn("Delete", result)

        name = self.random_string()
        form = {"name": name, "group": "other"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Edit transaction categories", result)

        with p.get_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.id_ == t_cat_id)
                .first()
            )
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            self.assertEqual(t_cat.name, name)
            self.assertEqual(t_cat.group, TransactionCategoryGroup.OTHER)

        e_str = "Transaction category name must be at least 3 characters long"
        form = {"name": "ab", "group": "other"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(e_str, result)

        e_str = "Transaction group must not be None"
        form = {"name": "ab", "group": ""}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(e_str, result)

        with p.get_session() as s:
            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.locked.is_(True))
            t_cat = query.first()
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            t_cat_uri = t_cat.uri

        endpoint = f"/h/txn-categories/c/{t_cat_uri}/edit"
        form = {"name": "abc", "group": "other"}
        self.web_post(endpoint, rc=403, data=form)

    def test_delete(self) -> None:
        p = self._portfolio

        today = datetime.date.today()

        with p.get_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.locked.is_(False))
                .first()
            )
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            t_cat_uri = t_cat.uri

            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            s.add(acct)
            s.commit()

            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat.id_,
            )
            s.add_all((txn, t_split))
            s.commit()

            t_split_id = t_split.id_

        endpoint = f"/h/txn-categories/c/{t_cat_uri}/delete"
        result, _ = self.web_get(endpoint)
        self.assertIn("Are you sure you want to delete this category?", result)

        result, _ = self.web_post(endpoint)
        self.assertIn("Edit transaction categories", result)

        with p.get_session() as s:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.id_ == t_split_id)
            t_split: TransactionSplit = query.scalar()

            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.id_ == t_split.category_id)
            t_cat = query.scalar()

            self.assertEqual(t_cat.name, "Uncategorized")

        with p.get_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.locked.is_(True))
                .first()
            )
            if t_cat is None:
                self.fail("TransactionCategory is missing")
            t_cat_uri = t_cat.uri

        endpoint = f"/h/txn-categories/c/{t_cat_uri}/delete"
        self.web_post(endpoint, rc=403)
