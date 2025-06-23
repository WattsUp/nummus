from __future__ import annotations

import datetime
import re
from decimal import Decimal

from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    AssetValuation,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestPerformance(WebTestBase):
    def setUp(self, **_) -> None:
        self.skipTest("Controller tests not updated yet")

    def test_page(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()
        with p.begin_session() as s:
            Asset.add_indices(s)

        endpoint = "performance.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        result = result.replace("\n", " ")
        self.assertRegex(
            result,
            r"(Total).*(\$0\.00).*(\$0\.00).*(\$0\.00).*(\$0\.00).*(0\.00%)",
        )
        self.assertRegex(
            result,
            r'<script>performance\.update\(.*"values": \[.+\].*\)</script>',
        )

    def test_chart(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)

        a_uri_1 = d["a_uri_1"]

        a_id_1 = Asset.uri_to_id(a_uri_1)

        acct_name_0 = "Monkey Bank Investing"
        with p.begin_session() as s:
            acct_0 = Account(
                name=acct_name_0,
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            s.add(acct_0)
            s.flush()
            acct_id_0 = acct_0.id_
            acct_uri_0 = acct_0.uri

            Asset.add_indices(s)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            # Add funding
            txn = Transaction(
                account_id=acct_id_0,
                date=today - datetime.timedelta(days=2),
                amount=1000,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Transfers"],
            )
            s.add_all((txn, t_split))
            s.flush()

            # Buy the house
            txn = Transaction(
                account_id=acct_id_0,
                date=today - datetime.timedelta(days=1),
                amount=-1000,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_1,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))

        endpoint = "performance.chart"
        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertNotIn("<html", result)
        self.assertRegex(
            result,
            r"<script>performance\.update\(.*"
            r'"min": null.*"values": \[.+\].*\)</script>',
        )
        self.assertIn('<div id="performance-config"', result)
        m = re.search(
            r"<script>performance\.update\(.*"
            r'"index": \[([^\]]+)\].*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        index_s = m[1] if m else ""
        dates_s = m[2] if m else ""
        self.assertIn(today.isoformat(), dates_s)
        self.assertEqual(index_s, '"0", "0", "0"')
        self.assertIn('"date_mode": "days"', result)
        # Get the asset block
        m = re.search(r'id="accounts"(.*)id="performance-chart-data"', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="accounts-total"')

        self.assertIn(f'id="account-{acct_uri_0}"', result_assets)
        self.assertRegex(
            result_total,
            r"(Total).*(\$1,000\.00).*(\$0\.00).*(\$0\.00).*(-\$1,000\.00).*(-100\.00%)",
        )

        with p.begin_session() as s:
            av = AssetValuation(
                asset_id=a_id_1,
                date_ord=today_ord - 100,
                value=1000,
            )
            s.add(av)

            # Add index valuations
            a_index_id = s.query(Asset.id_).where(Asset.name == "S&P 500").one()[0]
            av = AssetValuation(
                asset_id=a_index_id,
                date_ord=today_ord - 1,
                value=100,
            )
            s.add(av)
            av = AssetValuation(
                asset_id=a_index_id,
                date_ord=today_ord,
                value=101,
            )
            s.add(av)

            # Sell the house
            txn = Transaction(
                account_id=acct_id_0,
                date=today,
                amount=1001,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_1,
                asset_quantity_unadjusted=-1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))

        result, _ = self.web_get(
            (endpoint, {"period": "30-days"}),
        )
        self.assertRegex(
            result,
            r"<script>performance\.update\(.*"
            r'index": \[.+\].*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)
        m = re.search(
            r'<script>performance\.update\(.*"index": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        index_s = m[1] if m else ""
        twrr = [Decimal(0)] * 31
        twrr[-1] = Decimal("0.01")
        self.assertEqual(index_s, ", ".join(f'"{v}"' for v in twrr))

        result, _ = self.web_get(
            (endpoint, {"period": "90-days", "index": "Dow Jones Industrial Average"}),
        )
        self.assertIn('"date_mode": "months"', result)
        m = re.search(
            r'<script>performance\.update\(.*"index": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        index_s = m[1] if m else ""
        twrr = [Decimal(0)] * 91
        self.assertEqual(index_s, ", ".join(f'"{v}"' for v in twrr))

        # For long periods, downsample to min/avg/max
        result, _ = self.web_get(
            (endpoint, {"period": "5-years"}),
        )
        self.assertRegex(
            result,
            r"<script>performance\.update\(.*"
            r'index": \[.+\].*"min": \[.+\].*\)</script>',
        )
        m = re.search(
            r'<script>performance\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
        self.assertIn('"date_mode": "years"', result)

        # Add a closed Account with no transactions
        acct_name_1 = self.random_string()
        with p.begin_session() as s:
            acct = Account(
                name=acct_name_1,
                institution=self.random_string(),
                closed=True,
                category=AccountCategory.INVESTMENT,
                budgeted=True,
            )
            s.add(acct)
            s.flush()
            acct_id_1 = acct.id_
            acct_uri_1 = acct.uri

        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertNotIn(acct_name_1, result)

        # With a Transaction, the closed account should show up
        with p.begin_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id_1,
                date=today,
                amount=1000,
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
                account_id=acct_id_1,
                date=today - datetime.timedelta(days=1),
                amount=-1000,
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
        self.assertIn(acct_name_1, result)
        # Get the asset block
        m = re.search(r'id="accounts"(.*)id="performance-chart-data"', result, re.S)
        self.assertIsNotNone(m)
        result_assets = m[1] if m else ""
        result_assets = result_assets.replace("\n", " ")
        result_assets, result_total = result_assets.split('id="accounts-total"')

        self.assertIn(f'id="account-{acct_uri_0}"', result_assets)
        self.assertIn(f'id="account-{acct_uri_1}"', result_assets)
        self.assertRegex(
            result_assets.split(f'id="account-{acct_uri_1}"')[0],
            rf"({acct_name_0}).*"
            r"(\$1,000\.00).*(\$0\.00).*(\$1,001\.00).*(\$1\.00).*(44\.06%)",
        )
        self.assertRegex(
            result_assets.split(f'id="account-{acct_uri_1}"')[1],
            rf"({acct_name_1}).*"
            r"(\$0\.00).*(\$1,000\.00).*(\$1,000\.00).*(\$0\.00).*(0\.00%)",
        )
        self.assertRegex(
            result_total,
            r"(Total).*(\$1,000\.00).*(\$1,000\.00).*(\$2,001\.00).*(\$1\.00).*(44\.06%)",
        )

        # But if closed and period doesn't include the transaction then ignore
        # Closed accounts have zero balance so the updated_on date is the date it became
        # zero
        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertNotIn(acct_name_1, result)

    def test_dashboard(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()

        a_uri_1 = d["a_uri_1"]

        a_id_1 = Asset.uri_to_id(a_uri_1)

        acct_name_0 = "Monkey Bank Investing"
        with p.begin_session() as s:
            acct_0 = Account(
                name=acct_name_0,
                institution="Monkey Bank",
                category=AccountCategory.INVESTMENT,
                closed=False,
                budgeted=True,
            )
            s.add(acct_0)
            s.flush()
            acct_id_0 = acct_0.id_

            Asset.add_indices(s)

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            # Add funding
            txn = Transaction(
                account_id=acct_id_0,
                date=today - datetime.timedelta(days=2),
                amount=1000,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=categories["Transfers"],
            )
            s.add_all((txn, t_split))
            s.flush()

            # Buy the house
            txn = Transaction(
                account_id=acct_id_0,
                date=today - datetime.timedelta(days=1),
                amount=-1000,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                asset_id=a_id_1,
                asset_quantity_unadjusted=1,
                category_id=categories["Securities Traded"],
            )
            s.add_all((txn, t_split))
            s.flush()

            # Add index valuations
            a_index_id = s.query(Asset.id_).where(Asset.name == "S&P 500").one()[0]
            av = AssetValuation(
                asset_id=a_index_id,
                date_ord=today_ord - 1,
                value=100,
            )
            s.add(av)
            av = AssetValuation(
                asset_id=a_index_id,
                date_ord=today_ord,
                value=101,
            )
            s.add(av)
            s.flush()

            indices = [
                name
                for name, in s.query(Asset.name)
                .where(Asset.category == AssetCategory.INDEX)
                .all()
            ]

        endpoint = "performance.dashboard"
        result, _ = self.web_get(endpoint)
        self.assertNotIn("<html", result)
        result = result.replace("\n", " ")
        self.assertRegex(
            result,
            r"(-\$1,000\.00).*(-100\.00%).*"
            + ".*".join(
                rf"({name}).*({1 if name == 'S&P 500' else 0}\.00%)" for name in indices
            ),
        )
