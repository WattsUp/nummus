"""Test module nummus.controllers.transaction_category
"""

import datetime

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
    """Test transaction category controller"""

    def test_overlay(self):
        p = self._portfolio

        with p.get_session() as s:
            n = s.query(TransactionCategory).count()

        endpoint = "/h/txn-categories"
        result, _ = self.web_get(endpoint)
        self.assertEqual(n, result.count("txn-category"))
        self.assertIn("Edit transaction categories", result)

    def test_new(self):
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
            self.assertEqual(n_before + 1, n_after)

        e_str = "Transaction category name must be unique"
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(e_str, result)

        with p.get_session() as s:
            n_after = s.query(TransactionCategory).count()
            self.assertEqual(n_before + 1, n_after)

    def test_edit(self):
        p = self._portfolio

        with p.get_session() as s:
            query = s.query(TransactionCategory.uuid)
            query = query.where(TransactionCategory.locked.is_(False))
            (t_cat_uuid,) = query.first()

        endpoint = f"/h/txn-categories/{t_cat_uuid}/edit"
        result, _ = self.web_get(endpoint)
        self.assertIn("Delete", result)

        name = self.random_string()
        form = {"name": name, "group": "other"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn("Edit transaction categories", result)

        with p.get_session() as s:
            t_cat = (
                s.query(TransactionCategory)
                .where(TransactionCategory.uuid == t_cat_uuid)
                .first()
            )
            self.assertEqual(t_cat.name, name)
            self.assertEqual(t_cat.group, TransactionCategoryGroup.OTHER)

        e_str = "Transaction category name must be at least 3 characters long"
        form = {"name": "ab", "group": "other"}
        result, _ = self.web_post(endpoint, data=form)
        self.assertIn(e_str, result)

        with p.get_session() as s:
            query = s.query(TransactionCategory.uuid)
            query = query.where(TransactionCategory.locked.is_(True))
            (t_cat_uuid,) = query.first()

        endpoint = f"/h/txn-categories/{t_cat_uuid}/edit"
        form = {"name": "abc", "group": "other"}
        self.web_post(endpoint, rc=403, data=form)

    def test_delete(self):
        p = self._portfolio

        today = datetime.date.today()

        with p.get_session() as s:
            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.locked.is_(False))
            t_cat = query.first()
            t_cat_uuid = t_cat.uuid

            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            s.add(acct)
            s.commit()

            txn = Transaction(
                account_id=acct.id,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount, parent=txn, category_id=t_cat.id
            )
            s.add_all((txn, t_split))
            s.commit()

            t_split_uuid = t_split.uuid

        endpoint = f"/h/txn-categories/{t_cat_uuid}/delete"
        result, _ = self.web_get(endpoint)
        self.assertIn("Are you sure you want to delete this category?", result)

        result, _ = self.web_post(endpoint)
        self.assertIn("Edit transaction categories", result)

        with p.get_session() as s:
            query = s.query(TransactionSplit)
            query = query.where(TransactionSplit.uuid == t_split_uuid)
            t_split: TransactionSplit = query.scalar()

            query = s.query(TransactionCategory)
            query = query.where(TransactionCategory.id == t_split.category_id)
            t_cat: TransactionCategory = query.scalar()

            self.assertEqual("Uncategorized", t_cat.name)

        with p.get_session() as s:
            query = s.query(TransactionCategory.uuid)
            query = query.where(TransactionCategory.locked.is_(True))
            (t_cat_uuid,) = query.first()

        endpoint = f"/h/txn-categories/{t_cat_uuid}/delete"
        self.web_post(endpoint, rc=403)
