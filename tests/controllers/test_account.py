from __future__ import annotations

import datetime

from nummus.models import (
    Account,
    AccountCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestAccount(WebTestBase):
    def test_edit(self) -> None:
        p = self._portfolio

        today = datetime.date.today()

        with p.get_session() as s:
            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
            )
            s.add(acct)
            s.commit()

            acct_uri = acct.uri

            categories: dict[str, TransactionCategory] = {
                cat.name: cat for cat in s.query(TransactionCategory).all()
            }
            t_cat = categories["Uncategorized"]

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

        endpoint = f"/h/accounts/a/{acct_uri}/edit"
        result, _ = self.web_get(endpoint)
        self.assertIn("Edit account", result)

        name = self.random_string()
        institution = self.random_string()
        form = {"institution": institution, "name": name, "category": "credit"}
        result, headers = self.web_post(endpoint, data=form)
        self.assertEqual("update-account", headers["HX-Trigger"])
        with p.get_session() as s:
            acct = s.query(Account).first()
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
