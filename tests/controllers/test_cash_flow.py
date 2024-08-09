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

        endpoint = "cash_flow.page"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("income-pie-chart-canvas", result)
        self.assertRegex(
            result,
            r'<script>cashFlowChart\.update\(.*"totals": \[.+\].*\)</script>',
        )
        self.assertNotIn("Uncategorized", result)

    def test_txns(self) -> None:
        p = self._portfolio
        d = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_ord = yesterday.toordinal()

        t_split_0 = d["t_split_0"]
        t_split_1 = d["t_split_1"]
        cat_0 = d["cat_0"]

        endpoint = "cash_flow.txns"
        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
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
        self.assertRegex(result, rf"<div .*>{cat_0}</div>")
        self.assertRegex(result, r"<div .*>\$100.00</div>")
        self.assertRegex(result, rf'hx-get="/h/transactions/t/{t_split_0}/edit"')
        self.assertNotRegex(result, rf'hx-get="/h/transactions/t/{t_split_1}/edit"')

        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        # Second call for table should not update chart as well
        self.assertNotRegex(result, r"<script>cashFlowChart\.update\(.*\)</script>")

        result, _ = self.web_get(
            (endpoint, {"period": "30-days", "account": "None selected"}),
        )
        self.assertRegex(
            result,
            r"<script>cashFlowChart\.update\(.*"
            r'"chart_bars": false.*"totals": \[.+\].*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)
        self.assertNotIn("No matching transactions for given query filters", result)
        self.assertRegex(result, r"<title>Cash Flow, 30 Days \| nummus</title>")

        result, _ = self.web_get(
            (endpoint, {"period": "90-days"}),
        )
        self.assertIn('"date_mode": "months"', result)

        # For long periods, downsample to min/avg/max
        result, _ = self.web_get(
            (endpoint, {"period": "5-years"}),
        )
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

        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
        self.assertIn("Interest", result)
        self.assertIn("Groceries", result)
        self.assertNotIn("Uncategorized", result)

        result, _ = self.web_get(
            (endpoint, {"period": "1-year"}),
        )
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

        result, _ = self.web_get(
            (endpoint, {"period": "all"}),
        )
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
        result, _ = self.web_get((endpoint, queries))
        self.assertIn(t_cat, result)

        # But if closed and period doesn't include the transaction then ignore
        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get((endpoint, queries))
        self.assertNotIn(t_cat, result)

    def test_txns_options(self) -> None:
        d = self._setup_portfolio()

        acct = d["acct"]
        d["payee_0"]
        d["payee_1"]
        d["t_split_0"]
        d["t_split_1"]
        cat_0 = d["cat_0"]
        tag_1 = d["tag_1"]

        endpoint = "cash_flow.txns_options"
        result, _ = self.web_get(
            (endpoint, {"field": "account"}),
        )
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{acct}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

        result, _ = self.web_get(
            (endpoint, {"field": "category", "period": "all"}),
        )
        self.assertNotIn("<html", result)
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+hx-get')
        self.assertNotIn("checked", result)
        self.assertNotIn("Uncategorized", result)

        result, _ = self.web_get(
            (endpoint, {"field": "category", "category": cat_0}),
        )
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, rf'value="{cat_0}"[ \n]+checked[ \n]+hx-get')

        result, _ = self.web_get(
            (endpoint, {"field": "tag"}),
        )
        self.assertEqual(result.count("span"), 2)
        self.assertRegex(result, r'value="\[blank\]"[ \n]+hx-get')
        self.assertNotRegex(result, rf'value="{tag_1}"[ \n]+hx-get')
        self.assertNotIn("checked", result)

    def test_dashboard(self) -> None:
        _ = self._setup_portfolio()
        today = datetime.date.today()

        endpoint = "cash_flow.dashboard"
        result, _ = self.web_get(
            (endpoint, {"period": "8-months"}),
        )
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
