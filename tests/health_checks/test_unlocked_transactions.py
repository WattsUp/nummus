from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.unlocked_transactions import UnlockedTransactions
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestUnlockedTransactions(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        c = UnlockedTransactions(p)
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

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=10,
                statement=self.random_string(),
                locked=False,
                linked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Transfers"],
            )
            s.add_all((txn, t_split))
            s.flush()
            t_id = t_split.id_
            t_uri = t_split.uri

        c = UnlockedTransactions(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_uri)
            uri = i.uri

        target = {
            uri: f"{today} - Monkey Bank Checking: $10.00 to [blank] is unlocked",
        }
        self.assertEqual(c.issues, target)

        # Solve all issues
        with p.begin_session() as s:
            # Should lock the parent and the child but okay for this test
            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {"locked": True},
            )

        c = UnlockedTransactions(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

        # Ignore unlinked
        with p.begin_session() as s:
            # Should lock the parent and the child but okay for this test
            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {"locked": False, "linked": False},
            )

        c = UnlockedTransactions(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
