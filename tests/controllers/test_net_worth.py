from __future__ import annotations

import datetime
import re

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
        _ = self._setup_portfolio()
        today = datetime.date.today()

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
