from __future__ import annotations

import io
import re
import warnings
from typing import TYPE_CHECKING
from unittest import mock

from nummus import controllers
from nummus import exceptions as exc
from nummus.controllers import common
from nummus.models import Asset, TransactionCategory, TransactionCategoryGroup
from nummus.web_utils import HTTP_CODE_OK
from tests.controllers.base import WebTestBase

if TYPE_CHECKING:
    import werkzeug


class TestCommon(WebTestBase):

    def test_ctx_base(self) -> None:
        p = self._portfolio
        with p.begin_session() as s:
            TransactionCategory.add_default(s)

        with self._flask_app.app_context():
            result = common.ctx_base()

        self.assertIsInstance(result.get("nav_items"), list)

    def test_dialog_swap(self) -> None:
        with self._flask_app.app_context():
            content = self.random_string()
            event = self.random_string()

            response = common.dialog_swap()
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertNotIn(content, html)
            self.assertNotIn("HX-Trigger", response.headers)

            response = common.dialog_swap(content, event)
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertIn(content, html)
            self.assertEqual(response.headers.get("HX-Trigger"), event)

    def test_error(self) -> None:
        p = self._portfolio

        with self._flask_app.app_context():
            e_str = self.random_string()
            html = common.error(e_str)
            self.assertValidHTML(html)
            self.assertIn(e_str, html)

            with p.begin_session() as s:
                t_cat = TransactionCategory(
                    group=TransactionCategoryGroup.TRANSFER,
                    locked=False,
                    is_profit_loss=False,
                    asset_linked=False,
                    essential=False,
                )

                with self.assertRaises(exc.IntegrityError) as cm, s.begin_nested():
                    s.add(t_cat)
                e: exc.IntegrityError = cm.exception
                e_str = "Transaction category name must not be empty"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)

                name = self.random_string()
                t_cat.emoji_name = name
                s.add(t_cat)
                s.flush()

                t_cat = TransactionCategory(
                    emoji_name=name,
                    group=TransactionCategoryGroup.TRANSFER,
                    locked=False,
                    is_profit_loss=False,
                    asset_linked=False,
                    essential=False,
                )
                with self.assertRaises(exc.IntegrityError) as cm, s.begin_nested():
                    s.add(t_cat)
                e: exc.IntegrityError = cm.exception
                e_str = "Transaction category name must be unique"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)

                t_cat = TransactionCategory(
                    emoji_name=self.random_string(),
                    group=TransactionCategoryGroup.INCOME,
                    locked=False,
                    is_profit_loss=False,
                    asset_linked=False,
                    essential=False,
                )
                s.add(t_cat)
                s.flush()

                with self.assertRaises(exc.IntegrityError) as cm, s.begin_nested():
                    s.query(TransactionCategory).where(
                        TransactionCategory.id_ == t_cat.id_,
                    ).update({"essential": True})
                e: exc.IntegrityError = cm.exception
                e_str = "Income cannot be essential"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)

    def test_page(self) -> None:
        _ = self._setup_portfolio()

        endpoint = "dashboard.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        result, headers = self.web_get(endpoint, headers=headers)
        self.assertIn("<title>", result)
        self.assertNotIn("<html", result)
        self.assertIn("Vary", headers, msg=f"Response lack Vary {result}")
        self.assertIn("HX-Request", headers["Vary"])

        result, headers = self.web_get(endpoint)
        self.assertIn("<title>", result)
        self.assertIn("<html", result)
        self.assertIn("Vary", headers, msg=f"Response lack Vary {result}")
        self.assertIn("HX-Request", headers["Vary"])

    def test_add_routes(self) -> None:
        controllers.add_routes(self._flask_app, debug=False)
        routes = self._flask_app.url_map
        for rule in routes.iter_rules():
            self.assertFalse(rule.endpoint.startswith("nummus.controllers."))
            self.assertFalse(rule.endpoint.startswith("."))
            self.assertTrue(rule.rule.startswith("/"))
            self.assertFalse(rule.rule.startswith("/d/"))
            self.assertFalse(rule.rule != "/" and rule.rule.endswith("/"))

    def test_follow_links(self) -> None:
        self.skipTest("Controllers not updated yet")
        p = self._portfolio
        _ = self._setup_portfolio()
        with p.begin_session() as s:
            Asset.add_indices(s)

        # Recursively click on every link checking that it is a valid link and valid
        # method
        visited: set[str] = set()

        # Save hx-delete for the end in case it does successfully delete something
        deletes: set[str] = set()

        def visit_all_links(url: str, method: str, *, hx: bool = False) -> None:
            request = f"{method} {url}"
            if request in visited:
                return
            visited.add(request)
            response: werkzeug.test.TestResponse | None = None
            try:
                data: dict[str, str] | None = None
                if method in ["POST", "PUT", "DELETE"]:
                    data = {
                        "name": "",
                        "institution": "",
                        "number": "",
                    }
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    with mock.patch("sys.stderr", new=io.StringIO()) as stderr:
                        response = self._client.open(
                            url,
                            method=method,
                            buffered=False,
                            follow_redirects=False,
                            headers={"HX-Request": "true"} if hx else None,
                            data=data,
                        )
                    stderr = stderr.getvalue()
                page = response.text
                self.assertEqual(
                    response.status_code,
                    HTTP_CODE_OK,
                    msg=stderr if stderr else f"{request} {page}",
                )
                self.assertEqual(response.content_type, "text/html; charset=utf-8")

            finally:
                if response is not None:
                    response.close()
            hrefs = list(re.findall(r'href="([\w\d/\-]+)"', page))
            hx_gets = list(re.findall(r'hx-get="([\w\d/\-]+)"', page))
            hx_puts = list(re.findall(r'hx-put="([\w\d/\-]+)"', page))
            hx_posts = list(re.findall(r'hx-post="([\w\d/\-]+)"', page))
            hx_deletes = list(re.findall(r'hx-delete="([\w\d/\-]+)"', page))
            page = ""  # Clear page so --locals isn't too noisy

            for link in hrefs:
                visit_all_links(link, "GET")
            # With hx requests, add HX-Request header
            for link in hx_gets:
                visit_all_links(link, "GET", hx=True)
            for link in hx_puts:
                visit_all_links(link, "PUT", hx=True)
            for link in hx_posts:
                visit_all_links(link, "POST", hx=True)
            deletes.update(hx_deletes)

        visit_all_links("/", "GET")
        for link in deletes:
            visit_all_links(link, "DELETE", hx=True)

    def test_metrics(self) -> None:
        d = self._setup_portfolio()

        acct_uri = d["acct_uri"]

        # Visit account page
        endpoint = "accounts.page"
        headers = {"HX-Request": "true"}  # Fetch main content only
        self.web_get((endpoint, {"uri": acct_uri}), headers=headers)

        endpoint = "accounts.txns"
        self.web_get((endpoint, {"uri": acct_uri}))

        endpoint = "prometheus_metrics"
        result, _ = self.web_get(
            endpoint,
            content_type="text/plain; version=0.0.4; charset=utf-8",
        )
        if isinstance(result, bytes):
            result = result.decode()
        self.assertIn("flask_exporter_info", result)
        self.assertIn("nummus_info", result)
        self.assertIn("flask_http_request_duration_seconds_count", result)
        self.assertIn('endpoint="accounts.page"', result)
        self.assertIn('endpoint="accounts.txns"', result)
