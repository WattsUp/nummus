from __future__ import annotations

import datetime
import re

from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestNetWorth(WebTestBase):
    def setUp(self, **_) -> None:
        self.skipTest("Controller tests not updated yet")

    def test_page(self) -> None:
        _ = self._setup_portfolio()

        endpoint = "net_worth.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Today's Balance <b>$90.00</b>", result)
        self.assertRegex(
            result,
            r'<script>netWorth\.update\(.*"accounts": \[.+\].*\)</script>',
        )

    def test_chart(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)

        a_uri_0 = d["a_uri_0"]
        a_uri_1 = d["a_uri_1"]

        a_id_1 = Asset.uri_to_id(a_uri_1)

        endpoint = "net_worth.chart"
        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertNotIn("<html", result)
        self.assertNotIn("Today's Balance", result)
        self.assertRegex(
            result,
            r"<script>netWorth\.update\(.*"
            r'accounts": \[.+\].*"min": null.*\)</script>',
        )
        self.assertIn('<div id="net-worth-config"', result)
        m = re.search(
            r'<script>netWorth\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertIn(today.isoformat(), dates_s)
        self.assertIn('"date_mode": "days"', result)
        # Get the asset block
        m = re.search(r'id="assets"(.*)id="net-worth-chart-data"', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="assets-total"')

        self.assertNotIn(f'id="asset-{a_uri_0}"', result_assets)
        self.assertNotIn(f'id="asset-{a_uri_1}"', result_assets)
        self.assertRegex(result_total, r"(Total).*(\$90\.00).*(\$0\.00)[^0-9]*")

        result, _ = self.web_get(
            (endpoint, {"period": "30-days", "category": "credit"}),
        )
        self.assertRegex(
            result,
            r"<script>netWorth\.update\(.*"
            r'accounts": \[.+\].*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)

        result, _ = self.web_get(
            (endpoint, {"period": "90-days", "category": "credit"}),
        )
        self.assertIn('"date_mode": "months"', result)

        # For long periods, downsample to min/avg/max
        result, _ = self.web_get(
            (endpoint, {"period": "5-years"}),
        )
        self.assertRegex(
            result,
            r"<script>netWorth\.update\(.*"
            r'accounts": \[.+\].*"min": \[.+\].*\)</script>',
        )
        m = re.search(
            r'<script>netWorth\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
        self.assertIn('"date_mode": "years"', result)

        # Add a closed Account with no transactions
        acct_name = self.random_string()
        with p.begin_session() as s:
            a = Account(
                name=acct_name,
                institution=self.random_string(),
                closed=True,
                category=AccountCategory.CASH,
                budgeted=True,
            )
            s.add(a)
            s.flush()
            acct_id = a.id_

        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertNotIn(acct_name, result)

        # With a Transaction, the closed account should show up
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date=today,
                amount=10,
                statement=self.random_string(),
                locked=True,
                linked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn, t_split))

            txn = Transaction(
                account_id=acct_id,
                date=today - datetime.timedelta(days=1),
                amount=-10,
                statement=self.random_string(),
                locked=True,
                linked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                asset_id=a_id_1,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))

        queries = {
            "period": "custom",
            "start": yesterday.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn(acct_name, result)
        # Get the asset block
        m = re.search(r'id="assets"(.*)id="net-worth-chart-data"', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="assets-total"')

        self.assertIn(f'id="asset-{a_uri_1}"', result_assets)
        self.assertRegex(
            result_assets,
            r"(Real Estate).*(Fruit Ct\. House).*"
            r"(1\.000000).*(\$0\.00).*(0\.00%).*(-\$10\.00)[^0-9]*",
        )
        self.assertNotIn(f'id="asset-{a_uri_0}"', result_assets)
        self.assertRegex(result_total, r"(Total).*(\$90\.00).*(-\$10\.00)[^0-9]*")

        # But if closed and period doesn't include the transaction then ignore
        # Closed accounts have zero balance so the updated_on date is the date it became
        # zero
        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertNotIn(acct_name, result)

        # Add a valuation for the house with zero profit
        with p.begin_session() as s:
            v = AssetValuation(
                asset_id=a_id_1,
                date_ord=today_ord - 2,
                value=10,
            )
            s.add(v)

        queries = {
            "period": "custom",
            "start": yesterday.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertIn(acct_name, result)
        # Get the asset block
        m = re.search(r'id="assets"(.*)id="net-worth-chart-data"', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="assets-total"')

        self.assertIn(f'id="asset-{a_uri_1}"', result_assets)
        self.assertRegex(
            result_assets,
            r"(Real Estate).*(Fruit Ct\. House).*"
            r"(1\.000000).*(\$10\.00).*(10\.00%).*(\$0\.00)[^0-9]*",
        )
        self.assertNotIn(f'id="asset-{a_uri_0}"', result_assets)
        self.assertRegex(result_total, r"(Total).*(\$100\.00).*(\$0\.00)[^0-9]*")

    def test_dashboard(self) -> None:
        _ = self._setup_portfolio()
        today = datetime.date.today()

        endpoint = "net_worth.dashboard"
        result, _ = self.web_get(endpoint)
        self.assertNotIn("<html", result)
        self.assertRegex(
            result,
            r'<script>netWorth\.updateDashboard\(.*"total": \[.+\].*\)</script>',
        )
        m = re.search(
            r"<script>netWorth\.updateDashboard\("
            r'.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertIn(today.isoformat(), dates_s)
