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


class TestNetWorth(WebTestBase):
    def test_page(self) -> None:
        _ = self._setup_portfolio()

        endpoint = "/net-worth"
        headers = {"Hx-Request": "true"}  # Fetch main content only
        result, _ = self.web_get(endpoint, headers=headers)
        self.assertIn("Today's Balance <b>$90.00</b>", result)
        self.assertRegex(
            result,
            r'<script>netWorthChart\.update\(.*"accounts": \[.+\].*\)</script>',
        )

    def test_chart(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()
        today = datetime.date.today()
        today_ord = today.toordinal()
        yesterday = today - datetime.timedelta(days=1)

        endpoint = "/h/net-worth/chart"
        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries)
        self.assertNotIn("Today's Balance", result)
        self.assertRegex(
            result,
            r"<script>netWorthChart\.update\(.*"
            r'accounts": \[.+\].*"min": null.*\)</script>',
        )
        self.assertIn('<div id="net-worth-config"', result)
        m = re.search(
            r'<script>netWorthChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
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
            r"<script>netWorthChart\.update\(.*"
            r'accounts": \[.+\].*"min": null.*\)</script>',
        )
        self.assertIn('"date_mode": "weeks"', result)

        queries = {"period": "90-days", "category": "credit"}
        result, _ = self.web_get(endpoint, queries)
        self.assertIn('"date_mode": "months"', result)

        # For long periods, downsample to min/avg/max
        queries = {"period": "5-years"}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r"<script>netWorthChart\.update\(.*"
            r'accounts": \[.+\].*"min": \[.+\].*\)</script>',
        )
        m = re.search(
            r'<script>netWorthChart\.update\(.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertNotIn(today.isoformat(), dates_s)
        self.assertIn(today.isoformat()[:7], dates_s)
        self.assertIn('"date_mode": "years"', result)

        # Add a closed Account with no transactions
        acct_name = self.random_string()
        with p.get_session() as s:
            a = Account(
                name=acct_name,
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
        self.assertNotIn(acct_name, result)

        # With a Transaction, the closed account should show up
        with p.get_session() as s:
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct_id,
                date_ord=today_ord,
                amount=10,
                statement=self.random_string(),
                locked=True,
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
                date_ord=today_ord - 1,
                amount=-10,
                statement=self.random_string(),
                locked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=self.random_string(),
                category_id=categories["Uncategorized"],
            )
            s.add_all((txn, t_split))
            s.commit()

        queries = {
            "period": "custom",
            "start": yesterday.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get(endpoint, queries)
        self.assertIn(acct_name, result)

        # But if closed and period doesn't include the transaction then ignore
        # Closed accounts have zero balance so the updated_on date is the date it became
        # zero
        queries = {
            "period": "custom",
            "start": today.isoformat(),
            "end": today.isoformat(),
        }
        result, _ = self.web_get(endpoint, queries)
        self.assertNotIn(acct_name, result)

    def test_dashboard(self) -> None:
        _ = self._setup_portfolio()
        today = datetime.date.today()

        endpoint = "/h/dashboard/net-worth"
        result, _ = self.web_get(endpoint)
        self.assertRegex(
            result,
            r'<script>netWorthChart\.updateDashboard\(.*"total": \[.+\].*\)</script>',
        )
        m = re.search(
            r"<script>netWorthChart\.updateDashboard\("
            r'.*"labels": \[([^\]]+)\].*\)</script>',
            result,
        )
        self.assertIsNotNone(m)
        dates_s = m[1] if m else ""
        self.assertIn(today.isoformat(), dates_s)
