from __future__ import annotations

from tests.controllers.base import WebTestBase


class TestDashboard(WebTestBase):
    def test_page(self) -> None:
        endpoint = "dashboard.page"
        result, _ = self.web_get(endpoint)
        target = '<!DOCTYPE html>\n<html lang="en-US">'
        self.assertEqual(result[: len(target)], target)
        target = "</html>"
        self.assertEqual(result[-len(target) :], target)

        # If request is a HTMX request, should only return main section, not whole page
        result, _ = self.web_get(endpoint, headers={"HX-Request": "true"})
        target = '<!DOCTYPE html>\n<html lang="en-US">'
        self.assertNotEqual(result[: len(target)], target)
        target = "</html>"
        self.assertNotEqual(result[-len(target) :], target)
        # Page should start with title then the section
        self.assertRegex(result, r"<title>[^\n]*</title>\n?<section")
        target = "</section>"
        self.assertEqual(result[-len(target) :], target)

        urls = [
            "/h/dashboard/net-worth",
            "/h/dashboard/emergency-fund",
            "/h/dashboard/cash-flow?period=8-months",
            "/h/dashboard/performance",
        ]
        for url in urls:
            self.assertIn(f'hx-get="{url}"', result)
        self.assertEqual(result.count("hx-get"), len(urls))
