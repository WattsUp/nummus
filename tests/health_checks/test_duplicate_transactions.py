from __future__ import annotations

import datetime
import secrets

from nummus import portfolio, utils
from nummus.health_checks.duplicate_transactions import DuplicateTransactions
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestDuplicateTransactions(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()
        today_ord = today.toordinal()

        c = DuplicateTransactions(p)
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
            s.commit()

            txn_id = txn.id_

        c = DuplicateTransactions(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            # Add a duplicate transaction
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
            s.commit()

        c = DuplicateTransactions(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)
            amount_raw = Transaction.amount.type.process_bind_param(amount, None)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, f"{acct_id}.{today_ord}.{amount_raw}")
            uri = i.uri

        target = {
            uri: f"{today} - Monkey Bank Checking {utils.format_financial(amount)}",
        }
        self.assertEqual(c.issues, target)

        # If the date on one changes, the issue will be resolved
        with p.get_session() as s:
            txn = s.query(Transaction).where(Transaction.id_ == txn_id).one()

            txn.date_ord = today_ord - 1
            s.commit()

        c = DuplicateTransactions(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)
