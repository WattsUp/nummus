from __future__ import annotations

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

        endpoint = "/h/net-worth/chart"
        queries = {"period": "all"}
        result, _ = self.web_get(endpoint, queries)
        self.assertNotIn("Today's Balance", result)
        self.assertRegex(
            result,
            r'<script>netWorthChart\.update\(.*"accounts": \[.+\].*\)</script>',
        )
        self.assertIn('<div id="net-worth-config"', result)

        queries = {"period": "all", "category": "credit"}
        result, _ = self.web_get(endpoint, queries)
        self.assertRegex(
            result,
            r'<script>netWorthChart\.update\(.*"accounts": \[\].*\)</script>',
        )
