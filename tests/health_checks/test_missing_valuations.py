from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.missing_valuations import MissingAssetValuations
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetValuation,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestMissingValuations(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

        c = MissingAssetValuations(p)
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

            a = Asset(
                name="Banana Inc.",
                category=AssetCategory.STOCKS,
                interpolate=False,
            )
            s.add(a)
            s.flush()
            a_id = a.id_
            a_uri = a.uri

            amount = self.random_decimal(-1, 1)
            txn = Transaction(
                account_id=acct_id,
                date=yesterday,
                amount=amount,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["securities traded"],
                asset_id=a_id,
                asset_quantity_unadjusted=self.random_decimal(1, 10),
            )
            s.add_all((txn, t_split))

        c = MissingAssetValuations(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, a_uri)
            uri = i.uri

        target = {
            uri: "Banana Inc. has no valuations",
        }
        self.assertEqual(c.issues, target)

        # Add a valuation but after the transaction
        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=a_id,
                date_ord=today_ord,
                value=self.random_decimal(1, 10),
            )
            s.add(v)

        c = MissingAssetValuations(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, a_uri)
            uri = i.uri

        target = {
            uri: (
                f"Banana Inc. has first transaction on {yesterday} before first"
                f" valuation on {today}"
            ),
        }
        self.assertEqual(c.issues, target)

        # Add a valuation on the transaction
        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=a_id,
                date_ord=yesterday_ord,
                value=self.random_decimal(1, 10),
            )
            s.add(v)

        c = MissingAssetValuations(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

        target = {}
        self.assertEqual(c.issues, target)
