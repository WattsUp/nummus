from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.empty_fields import EmptyFields
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestEmptyFields(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        c = EmptyFields(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            # Add a single transaction
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            acct = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
                # missing number
            )
            s.add(acct)
            s.flush()
            acct_id = acct.id_
            acct_uri = acct.uri

            a = Asset(
                name="Banana Inc.",
                category=AssetCategory.STOCKS,
                interpolate=False,
                # missing description
            )
            s.add(a)
            s.flush()
            a_id = a.id_
            a_uri = a.uri

            amount = self.random_decimal(-1, 1)
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=amount,
                statement=self.random_string(),
                # missing payee
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["uncategorized"],
                # missing category
            )
            s.add_all((txn, t_split))
            s.flush()
            t_id = t_split.id_
            t_uri = t_split.uri

        c = EmptyFields(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 4)

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == f"{acct_uri}.number")
                .one()
            )
            self.assertEqual(i.check, c.name)
            i_acct_uri = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == f"{a_uri}.description")
                .one()
            )
            self.assertEqual(i.check, c.name)
            i_a_uri = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == f"{t_uri}.category")
                .one()
            )
            self.assertEqual(i.check, c.name)
            i_t_category_uri = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == f"{t_uri}.payee")
                .one()
            )
            self.assertEqual(i.check, c.name)
            i_t_payee_uri = i.uri

        t_split_str = f"{today} - Monkey Bank Checking"
        target = {
            i_acct_uri: "Account Monkey Bank Checking      has an empty number",
            i_a_uri: "Asset Banana Inc.                 has an empty description",
            i_t_category_uri: f"{t_split_str} is uncategorized",
            i_t_payee_uri: f"{t_split_str} has an empty payee",
        }
        self.assertEqual(c.issues, target)

        # Solve all issues
        with p.begin_session() as s:
            t_cat_id = (
                s.query(TransactionCategory.id_)
                .where(
                    TransactionCategory.name == "savings",
                )
                .one()[0]
            )
            s.query(Account).where(Account.id_ == acct_id).update(
                {"number": self.random_string()},
            )

            s.query(Asset).where(Asset.id_ == a_id).update(
                {"description": self.random_string()},
            )

            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {
                    "category_id": t_cat_id,
                    "payee": self.random_string(),
                },
            )

        c = EmptyFields(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
