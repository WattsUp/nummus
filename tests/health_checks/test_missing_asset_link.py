from __future__ import annotations

import datetime
import secrets

from nummus import portfolio
from nummus.health_checks.missing_asset_link import MissingAssetLink
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestMissingAssetLink(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.datetime.now().astimezone().date()

        c = MissingAssetLink(p)
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

            # Securities Traded expect an asset
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["securities traded"],
                # Missing asset
                asset_quantity_unadjusted=1,
            )
            s.add_all((txn, t_split))
            s.flush()
            t_stocks_id = t_split.id_
            t_stocks_uri = t_split.uri

            # Interest does not expect an asset
            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=20,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["interest"],
                asset_id=a_id,
            )
            s.add_all((txn, t_split))
            s.flush()
            t_interest_id = t_split.id_
            t_interest_uri = t_split.uri

        c = MissingAssetLink(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 2)

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == t_stocks_uri)
                .one()
            )
            self.assertEqual(i.check, c.name)
            i_stocks_uri = i.uri

            i = (
                s.query(HealthCheckIssue)
                .where(HealthCheckIssue.value == t_interest_uri)
                .one()
            )
            self.assertEqual(i.check, c.name)
            i_interest_uri = i.uri

        target = {
            i_stocks_uri: (
                f"{today} - Monkey Bank Checking: -$10.00 Securities Traded does not"
                " have an asset"
            ),
            i_interest_uri: (
                f"{today} - Monkey Bank Checking: $20.00 Interest has an asset"
            ),
        }
        self.assertEqual(c.issues, target)

        with p.begin_session() as s:
            s.query(TransactionSplit).where(
                TransactionSplit.id_ == t_stocks_id,
            ).update({"asset_id": a_id})
            s.query(TransactionSplit).where(
                TransactionSplit.id_ == t_interest_id,
            ).update({"asset_id": None})

        c = MissingAssetLink(p)
        c.test()

        with p.begin_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

        target = {}
        self.assertEqual(c.issues, target)
