from __future__ import annotations

import datetime
import secrets
from decimal import Decimal

from nummus import portfolio
from nummus.health_checks.category_direction import CategoryDirection
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    query_count,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestCategoryDirection(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.datetime.now().astimezone().date()

        c = CategoryDirection(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = query_count(s.query(HealthCheckIssue))
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

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["other income"],
            )
            s.add_all((txn, t_split))
            s.flush()
            t_id = t_split.id_
            t_uri = t_split.uri

        c = CategoryDirection(p)
        c.test()

        with p.begin_session() as s:
            n = query_count(s.query(HealthCheckIssue))
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_uri)
            uri = i.uri

        target = {
            uri: (
                f"{today} - Monkey Bank Checking: -$10.00 to [blank] has negative "
                "amount with income category Other Income"
            ),
        }
        self.assertEqual(c.issues, target)

        # Check other direction
        with p.begin_session() as s:
            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {
                    "amount": Decimal(10),
                    "category_id": categories["general merchandise"],
                },
            )

        c = CategoryDirection(p)
        c.test()

        with p.begin_session() as s:
            n = query_count(s.query(HealthCheckIssue))
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_uri)
            uri = i.uri

        target = {
            uri: (
                f"{today} - Monkey Bank Checking: $10.00 to [blank] has positive "
                "amount with expense category General Merchandise"
            ),
        }
        self.assertEqual(c.issues, target)

        # Fix issues
        with p.begin_session() as s:
            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {
                    "amount": Decimal(-10),
                    "category_id": categories["general merchandise"],
                },
            )

        c = CategoryDirection(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = query_count(s.query(HealthCheckIssue))
            self.assertEqual(n, 0)
