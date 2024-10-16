from __future__ import annotations

import datetime
import secrets
import textwrap
from decimal import Decimal

from nummus import portfolio
from nummus.health_checks.unbalanced_transfers import UnbalancedTransfers
from nummus.models import (
    Account,
    AccountCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestUnbalancedTransfers(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)

        c = UnbalancedTransfers(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

            categories = TransactionCategory.map_name(s)
            categories = {v: k for k, v in categories.items()}
            t_cat_id_0 = categories["Transfers"]
            t_cat_id_1 = categories["Credit Card Payments"]

            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            acct_savings = Account(
                name="Monkey Bank Savings",
                institution="Monkey Bank",
                category=AccountCategory.CREDIT,
                closed=False,
                budgeted=True,
            )
            s.add_all((acct_checking, acct_savings))
            s.commit()
            acct_checking_id = acct_checking.id_
            acct_savings_id = acct_savings.id_

            # Good transfer amount but wrong category
            txn = Transaction(
                account_id=acct_checking_id,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id_0,
            )
            s.add_all((txn, t_split))
            s.commit()

            txn = Transaction(
                account_id=acct_checking_id,
                date=today,
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id_1,
            )
            s.add_all((txn, t_split))
            s.commit()

            txn = Transaction(
                account_id=acct_savings_id,
                date=today,
                amount=-100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id_0,
            )
            s.add_all((txn, t_split))
            s.commit()

            txn = Transaction(
                account_id=acct_savings_id,
                date=today,
                amount=10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id_0,
            )
            s.add_all((txn, t_split))
            s.commit()
            t_split_savings_id = t_split.id_

        c = UnbalancedTransfers(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, f"{today}")
            uri = i.uri

        # The balanced $100 transfer also on this day will not show up
        target = {
            uri: textwrap.dedent(
                f"""\
                {today}: Sum of transfers on this day are non-zero
                  Monkey Bank Checking:        -$10.00 Credit Card Payments
                  Monkey Bank Savings :        +$10.00 Transfers""",
            ),
        }
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            s.query(TransactionSplit).where(
                TransactionSplit.id_ == t_split_savings_id,
                TransactionSplit.amount == Decimal(10),
            ).update(
                {"category_id": t_cat_id_1},
            )
            s.commit()

            # Add another bad transfer
            txn = Transaction(
                account_id=acct_checking_id,
                date=yesterday,
                amount=20,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id_0,
            )
            s.add_all((txn, t_split))
            s.commit()

            txn = Transaction(
                account_id=acct_savings_id,
                date=yesterday,
                amount=Decimal("-20.1"),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat_id_0,
            )
            s.add_all((txn, t_split))
            s.commit()
            t_split_savings_id = t_split.id_

        c = UnbalancedTransfers(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, f"{yesterday}")
            uri = i.uri

        # The balanced $100 transfer also on this day will not show up
        target = {
            uri: textwrap.dedent(
                f"""\
                {yesterday}: Sum of transfers on this day are non-zero
                  Monkey Bank Checking:        +$20.00 Transfers
                  Monkey Bank Savings :        -$20.10 Transfers""",
            ),
        }
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            s.query(TransactionSplit).where(
                TransactionSplit.id_ == t_split_savings_id,
            ).update(
                {"amount": Decimal("-20")},
            )
            s.commit()

        c = UnbalancedTransfers(p)
        c.test()
        target = {}
        self.assertEqual(c.issues, target)
