from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.overdrawn_accounts import OverdrawnAccounts
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestOverdrawnAccounts(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()
        today_ord = today.toordinal()

        c = OverdrawnAccounts(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}

            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )
            acct_credit = Account(
                name="Monkey Bank Credit",
                institution="Monkey Bank",
                category=AccountCategory.CREDIT,
                closed=False,
                emergency=False,
            )
            s.add_all((acct_checking, acct_credit))
            s.commit()
            acct_checking_id = acct_checking.id_
            acct_checking_uri = acct_checking.uri
            acct_credit_id = acct_credit.id_

            txn = Transaction(
                account_id=acct_checking_id,
                date_ord=today_ord,
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn, t_split))
            s.commit()

            # Negative balance on credit accounts is okay
            txn = Transaction(
                account_id=acct_credit_id,
                date_ord=today_ord,
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn, t_split))
            s.commit()

        c = OverdrawnAccounts(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, f"{acct_checking_uri}.{today}")
            uri = i.uri

        target = {
            uri: f"{today} - Monkey Bank Checking -$10.00",
        }
        self.assertEqual(c.issues, target)

        # Add some cash a week ago
        with p.get_session() as s:
            txn = Transaction(
                account_id=acct_checking_id,
                date_ord=today_ord - 7,
                amount=20,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Other Income"],
            )
            s.add_all((txn, t_split))
            s.commit()

        c = OverdrawnAccounts(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)
