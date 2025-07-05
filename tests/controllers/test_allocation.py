from __future__ import annotations

import datetime

from nummus.models import (
    Asset,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestAllocation(WebTestBase):
    def test_page(self) -> None:
        d = self._setup_portfolio()
        p = self._portfolio
        today = datetime.datetime.now().astimezone().date()
        today_ord = today.toordinal()

        acct_id = d["acct_id"]
        asset_0_id = d["asset_0_id"]
        asset_0_uri = d["asset_0_uri"]
        asset_1_uri = d["asset_1_uri"]

        endpoint = "allocation.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertNotIn(asset_0_uri, result)
        self.assertNotIn("Item", result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn("Energy", result)

        # Add transaction and valuation
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}
            t_cat_id = categories["securities traded"]

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

            v = AssetValuation(
                asset_id=asset_0_id,
                value=100,
                date_ord=today_ord,
            )
            s.add(v)
            s.flush()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(asset_0_uri, result)
        self.assertIn("$100.00", result)
        self.assertNotIn(asset_1_uri, result)
        self.assertIn("Item", result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn("Energy", result)
        self.assertNotIn("$10.00", result)
        self.assertNotIn("$90.00", result)
        self.assertNotIn("10.00%", result)
        self.assertNotIn("90.00%", result)

        # Update sectors
        with p.begin_session() as s:
            a = s.query(Asset).where(Asset.id_ == asset_0_id).one()
            a.ticker = "BANANA_ETF"
            a.update_sectors()

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn(asset_0_uri, result)
        self.assertIn("$100.00", result)
        self.assertNotIn(asset_1_uri, result)
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
            t_cat_id = categories["securities traded"]

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=self.random_decimal(-1, 1),
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=asset_0_id,
                asset_quantity_unadjusted=-1,
                category_id=t_cat_id,
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(endpoint, headers=headers)
        self.assertNotIn(asset_0_uri, result)
        self.assertNotIn("Item", result)
        self.assertNotIn("Real Estate", result)
        self.assertNotIn("Energy", result)
