from __future__ import annotations

import datetime
import io
import re
import warnings
from decimal import Decimal
from typing import TYPE_CHECKING
from unittest import mock

from nummus import controllers
from nummus import exceptions as exc
from nummus.controllers import common
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    Budget,
    Transaction,
    TransactionCategory,
    TransactionCategoryGroup,
    TransactionSplit,
)
from tests.controllers.base import HTTP_CODE_OK, WebTestBase

if TYPE_CHECKING:
    import werkzeug


class TestCommon(WebTestBase):
    def test_sidebar(self) -> None:
        _ = self._setup_portfolio()
        endpoint = "common.sidebar"
        result, _ = self.web_get(endpoint)
        self.assertIn("Click to show", result)

        result, _ = self.web_get((endpoint, {"closed": "included"}))
        self.assertIn("Click to hide", result)

    def test_ctx_sidebar(self) -> None:
        p = self._portfolio
        with p.get_session() as s:
            TransactionCategory.add_default(s)

        today = datetime.date.today()

        with self._flask_app.app_context():
            result = common.ctx_sidebar()
        target = {
            "net-worth": Decimal(0),
            "assets": Decimal(0),
            "liabilities": Decimal(0),
            "assets-w": 0,
            "liabilities-w": 0,
            "include_closed": False,
            "n_closed": 0,
            "categories": {},
        }
        self.assertDictEqual(result, target)

        with p.get_session() as s:
            acct_checking = Account(
                name="Monkey Bank Checking",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
                budgeted=True,
            )
            acct_savings = Account(
                name="Monkey Bank Savings",
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=True,
                emergency=False,
                budgeted=True,
            )
            s.add_all((acct_checking, acct_savings))
            s.commit()

            acct_uri_checking = acct_checking.uri
            acct_uri_savings = acct_savings.uri

            categories: dict[str, TransactionCategory] = {
                cat.name: cat for cat in s.query(TransactionCategory).all()
            }
            t_cat = categories["Uncategorized"]

            txn = Transaction(
                account_id=acct_savings.id_,
                date=today,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat.id_,
            )
            s.add_all((txn, t_split))

            txn = Transaction(
                account_id=acct_checking.id_,
                date=today,
                amount=-50,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                category_id=t_cat.id_,
            )
            s.add_all((txn, t_split))

            s.commit()

        target_accounts = [
            {
                "institution": "Monkey Bank",
                "name": "Monkey Bank Checking",
                "updated_days_ago": 0,
                "value": Decimal("-50.000000"),
                "category": AccountCategory.CASH,
                "closed": False,
                "uri": acct_uri_checking,
            },
            {
                "institution": "Monkey Bank",
                "name": "Monkey Bank Savings",
                "updated_days_ago": 0,
                "value": Decimal("100.000000"),
                "category": AccountCategory.CASH,
                "closed": True,
                "uri": acct_uri_savings,
            },
        ]
        target = {
            "net-worth": Decimal("50.000000"),
            "assets": Decimal("100.000000"),
            "liabilities": Decimal("-50.000000"),
            "assets-w": Decimal("66.67"),
            "liabilities-w": Decimal("33.33"),
            "include_closed": True,
            "n_closed": 1,
            "categories": {
                AccountCategory.CASH: (Decimal("50.000000"), target_accounts),
            },
        }
        with self._flask_app.app_context():
            result = common.ctx_sidebar(include_closed=True)
        self.assertDictEqual(result, target)

        target_accounts = [target_accounts[0]]
        target = {
            "net-worth": Decimal("50.000000"),
            "assets": Decimal("100.000000"),
            "liabilities": Decimal("-50.000000"),
            "assets-w": Decimal("66.67"),
            "liabilities-w": Decimal("33.33"),
            "include_closed": False,
            "n_closed": 1,
            "categories": {
                AccountCategory.CASH: (Decimal("50.000000"), target_accounts),
            },
        }
        with self._flask_app.app_context():
            result = common.ctx_sidebar(include_closed=False)
        self.assertDictEqual(result, target)

    def test_empty(self) -> None:
        self.assertEqual(common.empty(), "")

    def test_overlay_swap(self) -> None:
        with self._flask_app.app_context():
            content = self.random_string()
            event_0 = self.random_string()
            event_1 = self.random_string()

            response = common.overlay_swap()
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertNotIn(content, html)
            self.assertNotIn("HX-Trigger", response.headers)

            response = common.overlay_swap(content, event_0)
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertIn(content, html)
            self.assertIn(
                "HX-Trigger",
                response.headers,
                msg=f"Response lack HX-Trigger {data}",
            )
            self.assertEqual(response.headers["HX-Trigger"], event_0)

            response = common.overlay_swap(content, [event_0, event_1])
            data: bytes = response.data
            html = data.decode()
            self.assertValidHTML(html)
            self.assertIn(content, html)
            self.assertIn(
                "HX-Trigger",
                response.headers,
                msg=f"Response lack HX-Trigger {data}",
            )
            self.assertEqual(response.headers["HX-Trigger"], f"{event_0},{event_1}")

    def test_error(self) -> None:
        p = self._portfolio

        today = datetime.date.today()
        today_ord = today.toordinal()

        with self._flask_app.app_context():
            e_str = self.random_string()
            html = common.error(e_str)
            self.assertValidHTML(html)
            self.assertIn(e_str, html)

            with p.get_session() as s:
                t_cat = TransactionCategory(
                    group=TransactionCategoryGroup.TRANSFER,
                    locked=False,
                    is_profit_loss=False,
                    asset_linked=False,
                    essential=False,
                )

                with self.assertRaises(exc.IntegrityError) as cm:
                    s.add(t_cat)
                    s.commit()
                e: exc.IntegrityError = cm.exception
                e_str = "Transaction category name must not be empty"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)
                s.rollback()

                name = self.random_string()
                t_cat.name = name
                s.add(t_cat)
                s.commit()

                t_cat = TransactionCategory(
                    name=name,
                    group=TransactionCategoryGroup.TRANSFER,
                    locked=False,
                    is_profit_loss=False,
                    asset_linked=False,
                    essential=False,
                )
                with self.assertRaises(exc.IntegrityError) as cm:
                    s.add(t_cat)
                    s.commit()
                e: exc.IntegrityError = cm.exception
                e_str = "Transaction category name must be unique"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)
                s.rollback()

                b = Budget()
                b.date_ord = today_ord
                b.amount = Decimal(1)
                with self.assertRaises(exc.IntegrityError) as cm:
                    s.add(b)
                    s.commit()
                e: exc.IntegrityError = cm.exception
                e_str = "Budget amount must be zero or negative"
                html = common.error(e)
                self.assertValidHTML(html)
                self.assertIn(e_str, html)
                s.rollback()

    def test_add_routes(self) -> None:
        controllers.add_routes(self._flask_app)
        routes = self._flask_app.url_map
        for rule in routes.iter_rules():
            self.assertFalse(rule.endpoint.startswith("nummus.controllers."))
            self.assertFalse(rule.endpoint.startswith("."))
            self.assertTrue(rule.rule.startswith("/"))
            self.assertFalse(rule.rule != "/" and rule.rule.endswith("/"))

    def test_follow_links(self) -> None:
        p = self._portfolio
        _ = self._setup_portfolio()
        with p.get_session() as s:
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
                            headers={"Hx-Request": "true"} if hx else None,
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
