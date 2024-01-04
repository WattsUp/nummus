from __future__ import annotations

import datetime
import re

from nummus.models import (
    Account,
    AccountCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests.controllers.base import WebTestBase


class TestCashFlow(WebTestBase):
    def test_page(self) -> None:
        _ = self._setup_portfolio()

        endpoint = "/cash-flow"
        queries = {"no-defer": ""}
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, queries, headers=headers)
        self.assertIn("income-pie-chart-canvas", result)
        self.assertRegex(
            result,
            r'<script>cashFlowChart\.update\(.*"totals": \[.+\].*\)</script>',
        )

    def test_chart(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

        endpoint = "/h/cash-flow/chart"
        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries)
        self.assertNotIn("income-pie-chart-canvas", result)
        self.assertRegex(
            result,
            r"<script>cashFlowChart\.update\(.*"
            r'"chart_bars": false.*"totals": \[.+\].*\)</script>',
        )
        self.assertIn("Interest", result)
        self.assertNotIn("Uncategorized", result)
        m = re.search(
            r'<script>cashFlowChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertIn(today.isoformat(), dates_s)
        self.assertIn('"date_mode": "days"', result)

        queries = {"period": "30-days", "category": "credit"}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r"<script>cashFlowChart\.update\(.*"
            r'"chart_bars": false.*"totals": \[.+\].*\)</script>',
        )
        self.assertNotIn("Interest", result)
        self.assertNotIn("Uncategorized", result)
        self.assertIn('"date_mode": "weeks"', result)

        queries = {"period": "90-days", "category": "credit"}
        result, _ = self.web_get(endpoint, queries)
        self.assertIn('"date_mode": "months"', result)

        # For long periods, downsample to min/avg/max
        queries = {"period": "5-years"}
        result, _ = self.web_get(endpoint, queries)
        self.assertNotRegex(
            result,
            r"<script>cashFlowChart\.update\(.*"
            r'"chart_bars": true.*"totals": \[.+\].*\)</script>',
        )
        self.assertIn("no-defer", result)
        self.assertIn("<script>cashFlowChart.defer()</script>", result)

        queries = {"period": "5-years", "no-defer": ""}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r"<script>cashFlowChart\.update\(.*"
            r'"chart_bars": true.*"totals": \[.+\].*\)</script>',
        )
        self.assertIn("Interest", result)
        self.assertNotIn("Uncategorized", result)
        m = re.search(
            r'<script>cashFlowChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:4], dates_s)
        self.assertIn('"date_mode": null', result)

        # Add an expense transaction
        with p.get_session() as s:
            acct_id = s.query(Account.id_).scalar()
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                category_id=categories["Groceries"],
            )
            s.add_all((txn, t_split))
            s.commit()

        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries)
        self.assertIn("Interest", result)
        self.assertIn("Groceries", result)
        self.assertNotIn("Uncategorized", result)

        queries = {"period": "1-year", "no-defer": ""}
        result, _ = self.web_get(endpoint, queries)
        self.assertIn("Interest", result)
        self.assertIn("Groceries", result)
        self.assertNotIn("Uncategorized", result)

        # Add a closed Account with no transactions
        t_cat = "Other Income"
        with p.get_session() as s:
            a = Account(
                name=self.random_string(),
                institution=self.random_string(),
                closed=True,
                category=AccountCategory.CASH,
                emergency=False,
            )
            s.add(a)
            s.commit()
            acct_id = a.id_

        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries)
        self.assertNotIn(t_cat, result)

        # With a Transaction, the closed account should show up
        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date_ord=yesterday_ord,
                amount=10,
                statement=self.random_string(),
                locked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                category_id=categories[t_cat],
            )
            s.add_all((txn, t_split))
            s.commit()

        queries = {
            "period": "custom",
            "start": yesterday.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get(endpoint, queries)
        self.assertIn(t_cat, result)

        # But if closed and period doesn't include the transaction then ignore
        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get(endpoint, queries)
        self.assertNotIn(t_cat, result)

    def test_dashboard(self) -> None:
        _ = self._setup_portfolio()
        today = datetime.date.today()

        endpoint = "/h/dashboard/cash-flow"
        queries = {"period": "8-months", "no-defer": ""}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r'<script>cashFlowChart\.updateDashboard\(.*"totals": \[.+\].*\)</script>',
        )
        m = re.search(
            r"<script>cashFlowChart\.updateDashboard\("
            r'.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
