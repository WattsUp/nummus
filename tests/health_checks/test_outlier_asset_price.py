from __future__ import annotations

import datetime
import secrets
from decimal import Decimal

from nummus import portfolio
from nummus.health_checks.outlier_asset_price import OutlierAssetPrice
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetSplit,
    AssetValuation,
    HealthCheckIssue,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.base import TestBase


class TestOutlierAssetPrice(TestBase):
    def test_check(self) -> None:
        path_db = self._TEST_ROOT.joinpath(f"{secrets.token_hex()}.db")
        p = portfolio.Portfolio.create(path_db)

        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

        c = OutlierAssetPrice(p)
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
            )
            s.add(acct)
            s.commit()
            acct_id = acct.id_

            a = Asset(
                name="Banana Inc.",
                category=AssetCategory.STOCKS,
                interpolate=False,
            )
            s.add(a)
            s.commit()
            a_id = a.id_

            # Transactions with zero quantity are exempt
            txn = Transaction(
                account_id=acct_id,
                date=yesterday,
                amount=10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Dividends Received"],
                asset_id=a_id,
                asset_quantity_unadjusted=0,
            )
            s.add_all((txn, t_split))
            s.commit()

            txn = Transaction(
                account_id=acct_id,
                date=yesterday,
                amount=-10,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Securities Traded"],
                asset_id=a_id,
                asset_quantity_unadjusted=1,
            )
            s.add_all((txn, t_split))
            s.commit()
            t_uri = t_split.uri

        c = OutlierAssetPrice(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_uri)
            uri = i.uri

        target = {
            uri: (
                f"{yesterday}: Banana Inc. was traded at $10.00 which is above"
                " valuation of $0.00"
            ),
        }
        self.assertEqual(c.issues, target)

        # Add a valuation but after the transaction
        with p.get_session() as s:
            # Bought asset for 10/share but valuation is at 5/share
            v = AssetValuation(
                asset_id=a_id,
                date_ord=yesterday_ord,
                value=20,
            )
            s.add(v)
            s.commit()

        c = OutlierAssetPrice(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 1)

            i = s.query(HealthCheckIssue).one()
            self.assertEqual(i.check, c.name)
            self.assertEqual(i.value, t_uri)
            uri = i.uri

        target = {
            uri: (
                f"{yesterday}: Banana Inc. was traded at $10.00 which is below"
                " valuation of $20.00"
            ),
        }
        self.assertEqual(c.issues, target)

        with p.get_session() as s:
            # Add the 2:1 split that was missing
            a_split = AssetSplit(
                asset_id=a_id,
                date_ord=today_ord,
                multiplier=Decimal("0.5"),
            )
            s.add(a_split)
            s.commit()

            a = s.query(Asset).where(Asset.id_ == a_id).one()
            a.update_splits()
            s.commit()

        c = OutlierAssetPrice(p)
        c.test()

        with p.get_session() as s:
            n = s.query(HealthCheckIssue).count()
            self.assertEqual(n, 0)

        target = {}
        self.assertEqual(c.issues, target)
