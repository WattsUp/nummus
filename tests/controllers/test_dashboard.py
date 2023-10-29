from __future__ import annotations

from tests.controllers.base import WebTestBase


class TestDashboard(WebTestBase):
    def test_page_home(self) -> None:
        endpoint = "/"
        result, _ = self.web_get(endpoint)
        target = '<!DOCTYPE html>\n<html lang="en-US">'
        self.assertEqual(result[: len(target)], target)
        target = "</html>"
        self.assertEqual(result[-len(target) :], target)

        # If request is a HTMX request, should only return main section, not whole pagef
        result, _ = self.web_get(endpoint, headers={"Hx-Request": "true"})
        target = '<!DOCTYPE html>\n<html lang="en-US">'
        self.assertNotEqual(result[: len(target)], target)
        target = "</html>"
        self.assertNotEqual(result[-len(target) :], target)
        target = "<section"
        self.assertEqual(result[: len(target)], target)
        target = "</section>"
        self.assertEqual(result[-len(target) :], target)
