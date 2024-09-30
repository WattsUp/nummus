from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.unlinked_transactions import UnlinkedTransactions
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestUnlinkedTransactions(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()

        c = UnlinkedTransactions(p)
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
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
                budgeted=True,
            )
            s.add(acct)
            s.commit()
            acct_id = acct.id_

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=10,
                statement=self.random_string(),
                locked=False,
                linked=False,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Transfers"],
            )
            s.add_all((txn, t_split))
            s.commit()
            t_id = t_split.id_
            t_uri = t_split.uri

        c = UnlinkedTransactions(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_uri)
            uri = i.uri

        target = {
            uri: f"{today} - Monkey Bank Checking: $10.00 to [blank] is unlinked",
        }
        self.assertEqual(c.issues, target)

        # Solve all issues
        with p.get_session() as s:
            # Should link the parent and the child but okay for this test
            s.query(TransactionSplit).where(TransactionSplit.id_ == t_id).update(
                {"linked": True},
            )
            s.commit()

        c = UnlinkedTransactions(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
