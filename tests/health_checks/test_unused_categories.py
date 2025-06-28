from __future__ import annotations

import datetime
import secrets
from decimal import Decimal

from nummus import portfolio, utils
from nummus.health_checks.unused_categories import UnusedCategories
from nummus.models import (
    Account,
    AccountCategory,
    BudgetAssignment,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestUnusedCategories(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.datetime.now().astimezone().date()

        # Lock all categories
        with p.begin_session() as s:
            s.query(TransactionCategory).update({"locked": True})

        c = UnusedCategories(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            s.query(TransactionCategory).where(
                TransactionCategory.name != "other income",
            ).delete()
            t_cat = s.query(TransactionCategory).one()
            t_cat.locked = False
            s.flush()
            t_cat_id = t_cat.id_
            t_cat_uri = t_cat.uri

        c = UnusedCategories(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_cat_uri)
            uri = i.uri

        target = {
            uri: "Other Income has no transactions or no budget assignments",
        }
        self.assertEqual(c.issues, target)

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
            acct_id = acct.id_

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=10,
                statement=self.random_string(),
                cleared=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

        c = UnusedCategories(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            # Only BudgetAssignments now
            s.query(TransactionSplit).delete()
            s.query(Transaction).delete()

            today = datetime.datetime.now().astimezone().date()
            month = utils.start_of_month(today)
            month_ord = month.toordinal()

            a = BudgetAssignment(
                month_ord=month_ord,
                amount=Decimal(100),
                category_id=t_cat_id,
            )
            s.add(a)

        c = UnusedCategories(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
