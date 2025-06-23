from __future__ import annotations

from tests.controllers.base import WebTestBase


class TestDashboard(WebTestBase):
    def test_page(self) -> None:
        endpoint = "dashboard.page"
        result, _ = self.web_get(endpoint)
        target = '<!DOCTYPE html><html lang="en-US">'
        self.assertEqual(result[: len(target)], target)
        target = "</html>"
        self.assertEqual(result[-len(target) :], target)

        # If request is a HTMX request, should only return main section, not whole page
        result, _ = self.web_get(endpoint, headers={"HX-Request": "true"})
        target = '<!DOCTYPE html><html lang="en-US">'
        self.assertNotEqual(result[: len(target)], target)
        target = "</html>"
        self.assertNotEqual(result[-len(target) :], target)
        # Page should start with title, nav.update, then main content
        self.assertRegex(
            result,
            r"<title>[^\n]*</title><script>nav\.update\(\)</script><div",
        )
        target = "</div>"
        self.assertEqual(result[-len(target) :], target)

        urls = [
            "/h/dashboard/emergency-fund",
        ]
        for url in urls:
            self.assertIn(f'hx-get="{url}"', result)
        self.assertEqual(result.count("hx-get"), len(urls))
