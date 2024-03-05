from __future__ import annotations

import datetime
import io
import re
import shutil
import time
import urllib.parse
import warnings
from typing import TYPE_CHECKING
from unittest import mock

import autodict
import flask
import flask.testing

from nummus import portfolio, sql, web
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetValuation,
    Budget,
    Credentials,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from tests import TEST_LOG
from tests.base import TestBase

if TYPE_CHECKING:
    import werkzeug


_RE_URI = re.compile(r"^[0-9a-f]{8}$")

ResultType = dict[str, object] | str | bytes
Tree = dict[str, "TreeNode"]
TreeNode = Tree | tuple[str, Tree] | object

HTTP_CODE_OK = 200
HTTP_CODE_BAD_REQUEST = 400


class WebTestBase(TestBase):
    def assertValidHTML(self, s: str) -> None:  # noqa: N802
        """Test HTML is valid based on tags.

        Args:
            s: String to test
        """
        tags: list[str] = re.findall(r"<(/?\w+)(?: [^<>]+)?>", s)

        tree: Tree = {"__parent__": (None, None)}
        current_node = tree
        for tag in tags:
            if not isinstance(current_node, dict):
                self.fail("current_node is not a dictionary")
            if tag[0] == "/":
                # Close tag
                item = current_node.pop("__parent__")
                if not isinstance(item, tuple):
                    self.fail("__parent__ is not a tuple")
                current_tag, parent = item
                current_node = parent
                self.assertEqual(current_tag, tag[1:])
            elif tag in ["link", "meta", "path", "input", "hr"]:
                # Tags without close tags
                current_node[tag] = {}
            else:
                current_node[tag] = {"__parent__": (tag, current_node)}
                current_node = current_node[tag]

        # Got back up to the root element
        if not isinstance(current_node, dict):
            self.fail("current_node is not a dictionary")
        item = current_node.pop("__parent__")
        if not isinstance(item, tuple):
            self.fail("__parent__ is not a tuple")
        tag, parent = item
        self.assertIn(tag, [None, "html"])  # <html> might not be closed
        if parent is not None:
            parent: dict[str, object]
            self.assertEqual(parent.keys(), {"__parent__", "html"})

    def _setup_portfolio(self) -> dict[str, str]:
        """Create accounts and transactions to test with.

        Returns:
            {
                "acct": Account name,
                "acct_uri": URI for Account,
                "t_0": URI for transaction 0
                "t_split_0": URI for split 0
                "t_1": URI for transaction 1
                "t_split_1": URI for split 1
                "payee_0": Payee for transaction 0
                "payee_1": Payee for transaction 1
                "cat_0": Payee for transaction 0
                "cat_1": Payee for transaction 1
                "tag_1": Tag for transaction 1
            }
        """
        self._clear_portfolio()
        p = self._portfolio

        today = datetime.date.today()
        today_ord = today.toordinal()

        acct_name = "Monkey Bank Checking"
        payee_0 = "Apple"
        payee_1 = "Banana"

        cat_0 = "Interest"
        cat_1 = "Uncategorized"

        tag_1 = self.random_string()

        with p.get_session() as s:
            acct = Account(
                name=acct_name,
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                emergency=False,
            )
            s.add(acct)
            s.commit()

            acct_uri = acct.uri

            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            txn = Transaction(
                account_id=acct.id_,
                date_ord=today_ord,
                amount=100,
                statement=self.random_string(),
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=payee_0,
                category_id=categories[cat_0],
            )
            s.add_all((txn, t_split))
            s.commit()

            t_0_uri = txn.uri
            t_split_0_uri = t_split.uri

            txn = Transaction(
                account_id=acct.id_,
                date_ord=today_ord,
                amount=-10,
                statement=self.random_string(),
                locked=True,
            )
            t_split = TransactionSplit(
                amount=txn.amount,
                parent=txn,
                payee=payee_1,
                category_id=categories[cat_1],
                tag=tag_1,
            )
            s.add_all((txn, t_split))
            s.commit()

            t_1_uri = txn.uri
            t_split_1_uri = t_split.uri

        return {
            "acct": acct_name,
            "acct_uri": acct_uri,
            "t_0": t_0_uri,
            "t_split_0": t_split_0_uri,
            "t_1": t_1_uri,
            "t_split_1": t_split_1_uri,
            "payee_0": payee_0,
            "payee_1": payee_1,
            "cat_0": cat_0,
            "cat_1": cat_1,
            "tag_1": tag_1,
        }

    def _clear_portfolio(self) -> None:
        """Clear all content from portfolio."""
        # Clean portfolio
        # In order of deletion, so children models first
        models = [
            AssetValuation,
            Budget,
            Credentials,
            TransactionSplit,
            Transaction,
            Asset,
            Account,
        ]
        with self._portfolio.get_session() as s:
            for model in models:
                for instance in s.query(model).all():
                    s.delete(instance)
                s.commit()

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._clean_test_root()

        # Create a portfolio for the test class
        path_db = cls._TEST_ROOT.joinpath("portfolio.db")
        cls._portfolio = portfolio.Portfolio.create(path_db, None)

        path_cert = cls._DATA_ROOT.joinpath("cert_ss.pem")
        path_key = cls._DATA_ROOT.joinpath("key_ss.pem")

        shutil.copyfile(path_cert, cls._portfolio.ssl_cert_path)
        shutil.copyfile(path_key, cls._portfolio.ssl_key_path)

        with (
            mock.patch("sys.stderr", new=io.StringIO()) as _,
            mock.patch("sys.stdout", new=io.StringIO()) as _,
        ):
            # Ignore SSL warnings
            s = web.Server(cls._portfolio, "127.0.0.1", 8080, debug=False)
        cls._flask_app: flask.Flask = s._app  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cls._client = cls._flask_app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        sql.drop_session()
        cls._clean_test_root()
        super().tearDownClass()

    def setUp(self, **_) -> None:
        self._original_render_template = flask.render_template

        self._called_context: dict[str, object] = {}

        def render_template(path: str, **context: dict[str, object]) -> str:
            self._called_context.clear()
            self._called_context.update(**context)
            return self._original_render_template(path, **context)

        flask.render_template = render_template

        super().setUp(clean=False)

    def tearDown(self, **_) -> None:
        flask.render_template = self._original_render_template

        self._clear_portfolio()
        super().tearDown(clean=False)

    def web_open(
        self,
        method: str,
        endpoint: str,
        queries: dict[str, str] | dict[str, str | list[str]] | None = None,
        rc: int = HTTP_CODE_OK,
        **kwargs: object,
    ) -> tuple[str, dict[str, str]]:
        """Run a test HTTP request.

        Args:
            method: HTTP method to use
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        if queries is None or len(queries) < 1:
            url = endpoint
        else:
            queries_flat = []
            for k, v in queries.items():
                v_list = [v] if isinstance(v, str) else v
                queries_flat.extend(
                    f"{k}={urllib.parse.quote(str(vv))}" for vv in v_list
                )
            url = f"{endpoint}?{'&'.join(queries_flat)}"

        kwargs["method"] = method
        response: werkzeug.test.TestResponse | None = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                start = time.perf_counter()
                if rc == HTTP_CODE_OK:
                    response = self._client.open(
                        url,
                        buffered=False,
                        follow_redirects=False,
                        **kwargs,
                    )
                else:
                    with mock.patch("sys.stderr", new=io.StringIO()) as _:
                        response = self._client.open(
                            url,
                            buffered=False,
                            follow_redirects=False,
                            **kwargs,
                        )
            duration = time.perf_counter() - start
            self.assertEqual(response.status_code, rc, msg=response.text)
            self.assertEqual(response.content_type, "text/html; charset=utf-8")

            with autodict.JSONAutoDict(str(TEST_LOG)) as d:
                # Replace uri with {accountURI, assetURI, ...}
                parts = []
                for p in endpoint.split("/"):
                    if _RE_URI.match(p):
                        parts.append("{uri}")
                    else:
                        parts.append(p)
                endpoint = "/".join(parts)
                k = f"{method:6} {endpoint}"
                if queries:
                    queries_flat = [f"{k}=<value>" for k in queries]
                    k += f"?{'&'.join(queries_flat)}"
                if k not in d["web_latency"]:
                    d["web_latency"][k] = []
                d["web_latency"][k].append(duration)

            # Fairly loose cause jinja and sql caching will save time
            self.assertLessEqual(duration, 0.5)  # All responses faster than 500ms

            html = response.text
            self.assertValidHTML(html)
            return html, response.headers
        finally:
            if response is not None:
                response.close()

    def web_get(
        self,
        endpoint: str,
        queries: dict[str, str] | dict[str, str | list[str]] | None = None,
        rc: int = HTTP_CODE_OK,
        **kwargs: object,
    ) -> tuple[str, dict[str, str]]:
        """Run a test HTTP GET request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "GET",
            endpoint,
            queries,
            rc=rc,
            **kwargs,
        )

    def web_put(
        self,
        endpoint: str,
        queries: dict[str, str] | dict[str, str | list[str]] | None = None,
        rc: int = HTTP_CODE_OK,
        **kwargs: object,
    ) -> tuple[str, dict[str, str]]:
        """Run a test HTTP PUT request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "PUT",
            endpoint,
            queries,
            rc=rc,
            **kwargs,
        )

    def web_post(
        self,
        endpoint: str,
        queries: dict[str, str] | dict[str, str | list[str]] | None = None,
        rc: int = HTTP_CODE_OK,
        **kwargs: object,
    ) -> tuple[str, dict[str, str]]:
        """Run a test HTTP POST request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "POST",
            endpoint,
            queries,
            rc=rc,
            **kwargs,
        )

    def web_delete(
        self,
        endpoint: str,
        queries: dict[str, str] | dict[str, str | list[str]] | None = None,
        rc: int = HTTP_CODE_OK,
        **kwargs: object,
    ) -> tuple[str, dict[str, str]]:
        """Run a test HTTP DELETE request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "DELETE",
            endpoint,
            queries,
            rc=rc,
            **kwargs,
        )
