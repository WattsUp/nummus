from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.unnecessary_slits import UnnecessarySplits
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestUnnecessarySplits(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        c = UnnecessarySplits(p)
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
            )
            s.add(acct)
            s.flush()
            acct_id = acct.id_

            amount = self.random_decimal(-1, 1)
            statement = self.random_string()
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=amount,
                statement=statement,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn, t_split))

        c = UnnecessarySplits(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            # Add a duplicate split
            amount = -self.random_decimal(10, 100)
            statement = self.random_string()
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=amount,
                statement=statement,
            )
            t_split_0 = TransactionSplit(
                amount=2,
                parent=txn,
                category_id=categories["Uncategorized"],
            )
            t_split_1 = TransactionSplit(
                amount=amount - 5,
                parent=txn,
                category_id=categories["Uncategorized"],
            )
            t_split_2 = TransactionSplit(
                amount=3,
                parent=txn,
                payee=self.random_string(),
                category_id=categories["General Merchandise"],
            )
            s.add_all((txn, t_split_0, t_split_1, t_split_2))
            s.flush()
            t_id = txn.id_
            t_split_id_0 = t_split_0.id_

        c = UnnecessarySplits(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()

            self.assertEqual(i.check, c.name)
            self.assertEqual(
                i.value,
                f"{t_id}.{None}.{categories['Uncategorized']}.{None}",
            )
            uri = i.uri

        target = {
            uri: f"{today} - Monkey Bank Checking -  - Uncategorized - ",
        }
        self.assertEqual(c.issues, target)

        # If the category on one changes, the issue will be resolved
        with p.begin_session() as s:
            t_split = (
                s.query(TransactionSplit)
                .where(TransactionSplit.id_ == t_split_id_0)
                .one()
            )

            t_split.category_id = categories["General Merchandise"]

        c = UnnecessarySplits(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
