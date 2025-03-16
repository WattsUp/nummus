from __future__ import annotations

import datetime

from nummus.models import (
    Account,
    Asset,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestAllocation(WebTestBase):
    def setUp(self, **_) -> None:
        self.skipTest("Controller tests not updated yet")

    def test_page(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.date.today()
        today_ord = today.toordinal()

        acct_uri = d["acct_uri"]
        a_0 = d["a_0"]
        a_1 = d["a_1"]
        a_uri_0 = d["a_uri_0"]
        acct_id = Account.uri_to_id(acct_uri)
        a_id_0 = Asset.uri_to_id(a_uri_0)

        endpoint = "allocation.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertNotIn(a_0, result)
        self.assertNotIn("Item", result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn("Energy", result)

        # Add transaction and valuation
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            t_cat_id = categories["Securities Traded"]

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_0,
                asset_quantity_unadjusted=1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

            v = AssetValuation(
                asset_id=a_id_0,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.flush()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(a_0, result)
        self.assertIn("$100.00", result)
        self.assertNotIn(a_1, result)
        self.assertIn("Item", result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn("Energy", result)
        self.assertNotIn("$10.00", result)
        self.assertNotIn("$90.00", result)
        self.assertNotIn("10.00%", result)
        self.assertNotIn("90.00%", result)

        # Update sectors
        with p.begin_session() as s:
            a = s.query(Asset).where(Asset.id_ == a_id_0).one()
            a.ticker = "BANANA_ETF"
            a.update_sectors()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(a_0, result)
        self.assertIn("$100.00", result)
        self.assertNotIn(a_1, result)
        self.assertIn("Item", result)
        self.assertIn("Real Estate", result)
        self.assertIn("Energy", result)
        self.assertIn("$10.00", result)
        self.assertIn("$90.00", result)
        self.assertIn("10.00%", result)
        self.assertIn("90.00%", result)

        # Selling asset will hide it
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            t_cat_id = categories["Securities Traded"]

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_0,
                asset_quantity_unadjusted=-1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertNotIn(a_0, result)
        self.assertNotIn("Item", result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn("Energy", result)
