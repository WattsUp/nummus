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
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.base import TestBase


class TestTypos(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()
        today_ord = today.toordinal()

        c = Typos(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
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
                emergency=False,
            )
            s.add(acct)
            s.commit()
            acct_id = acct.id_

            a = Asset(
                name="Bananana Inc.",
                category=AssetCategory.STOCKS,
                interpolate=False,
                description="Technologie/Stuff",
            )
            s.add(a)
            s.commit()
            a_id = a.id_

            amount = self.random_decimal(-1, 1)
            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord,
                amount=amount,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Uncategorized"],
                payee="Grocery Storre",
                description="Applesandbananas",
                tag="Froooot/",
            )
            s.add_all((txn, t_split))
            s.commit()
            t_id = t_split.id_

            t_cat = TransactionCategory(
                name="Stonks",
                group=TransactionCategoryGroup.OTHER,
                locked=False,
                is_profit_loss=True,
            )
            s.add(t_cat)
            s.commit()
            t_cat_id = t_cat.id_

        c = Typos(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 8)

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "bannke")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_0 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "moonkey")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_1 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "bananana")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_2 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "technologie")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_3 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "storre")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_4 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "applesandbananas")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_5 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "froooot")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_6 = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == "stonks")
                .one()
            )
            self.assertEqual(i.check, c.name)
            uri_7 = i.uri

        target = {
            uri_0: "Account Monkey Bannke Checking      name       : Bannke",
            uri_1: "Account Monkey Bannke Checking      institution: Moonkey",
            uri_2: "Asset Bananana Inc.                 name       : Bananana",
            uri_3: "Asset Bananana Inc.                 description: Technologie",
            uri_4: f"{today} - Monkey Bannke Checking payee      : Storre",
            uri_5: f"{today} - Monkey Bannke Checking description: Applesandbananas",
            uri_6: f"{today} - Monkey Bannke Checking tag        : Froooot",
            uri_7: "Txn category Stonks                 name       : Stonks",
        }
        self.assertEqual(c.issues, target)

        # Solve all issues
        with p.get_session() as s:
            s.query(Account).where(Account.id_ == acct_id).update(
                {
                    "name": "Monkey Bank Checking",
                    "institution": "Monkey Bank",
                },
            )

            s.query(Asset).where(Asset.id_ == a_id).update(
                {
                    "name": "Banana Inc.",
                    "description": "Technology/Stuff",
                },
            )

            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {
                    "payee": "Grocery Store",
                    "description": "Apples and Bananas",
                    "tag": None,
                },
            )

            s.query(TransactionCategory).where(
                TransactionCategory.id_ == t_cat_id,
            ).update(
                {
                    "name": "Stocks",
                },
            )
            s.commit()

        c = Typos(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
