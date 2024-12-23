from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.typos import Typos
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


class TestTypos(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        c = Typos(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            # Add a single transaction
            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            acct_0 = Account(
                name="Monkey Bannke Checking",
                institution="Moonkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct_0)
            s.flush()
            acct_id_0 = acct_0.id_

            acct_1 = Account(
                name="Monkey Bannke Savings",
                institution="Moonkey Bannke",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct_1)
            s.flush()
            acct_id_1 = acct_1.id_

            a = Asset(
                name="Bananana Inc.",
                category=AssetCategory.STOCKS,
                interpolate=False,
                description="Technologie//Stuff",
            )
            s.add(a)
            s.flush()
            a_id = a.id_

            amount_0 = self.random_decimal(-1, 1)
            txn_0 = Transaction(
                account_id=acct_id_0,
                date=today,
                amount=amount_0,
                statement=self.random_string(),
            )
            t_split_0 = TransactionSplit(
                amount=txn_0.amount,
                parent=txn_0,
                category_id=categories["Uncategorized"],
                payee="Grocery Storre",
                description="$ 5 Applesandbananas",
                tag="Fruit",
            )
            s.add_all((txn_0, t_split_0))
            s.flush()
            t_id_0 = t_split_0.id_

            amount_1 = self.random_decimal(-1, 1)
            txn_1 = Transaction(
                account_id=acct_id_1,
                date=today,
                amount=amount_1,
                statement=self.random_string(),
            )
            t_split_1 = TransactionSplit(
                amount=txn_1.amount,
                parent=txn_1,
                category_id=categories["Uncategorized"],
                payee="Grocery Store",
                tag="Fruiit",
            )
            s.add_all((txn_1, t_split_1))
            s.flush()
            t_id_1 = t_split_1.id_

        c = Typos(p, no_description_typos=True)
        c.test()

        with p.begin_session() as s:
            # Ignore description typos but issue still exists
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 5)

            n = len(c.issues)
            self.assertEqual(n, 3)

        c = Typos(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 5)

            n = len(c.issues)
            self.assertEqual(n, 5)

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "Moonkey Bannke")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_0 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "Grocery Storre")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_1 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "Fruiit")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_2 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "applesandbananas")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_3 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "technologie")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_4 = i.uri

        target = {
            uri_0: "Account Monkey Bannke Savings       institution: Moonkey Bannke",
            uri_1: f"{today} - Monkey Bannke Checking payee      : Grocery Storre",
            uri_2: f"{today} - Monkey Bannke Savings  tag        : Fruiit",
            uri_3: f"{today} - Monkey Bannke Checking description: applesandbananas",
            uri_4: "Asset Bananana Inc.                 description: technologie",
        }
        self.assertEqual(c.issues, target)

        # Solve all issues
        with p.begin_session() as s:
            s.query(Account).where(Account.id_ == acct_id_0).update(
                {
                    "name": "Monkey Bank Checking",
                    "institution": "Monkey Bank",
                },
            )

            s.query(Account).where(Account.id_ == acct_id_1).update(
                {
                    "name": "Monkey Bank Savings",
                    "institution": "Monkey Bank",
                },
            )

            s.query(Asset).where(Asset.id_ == a_id).update(
                {
                    "name": "Banana Inc.",
                    "description": None,
                },
            )

            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id_0).update(
                {
                    "payee": "Grocery Store",
                    "description": "Apples and Bananas",
                },
            )

            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id_1).update(
                {
                    "description": "Apples and Bananas",
                    "tag": None,
                },
            )

        c = Typos(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

    def test_ignore(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        c = Typos(p)
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
                name="Monkey Bannke Checking",
                institution="Moonkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)

        Typos.ignore(p, {"Bannke", "Moonkey"})
        c = Typos(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)
