from __future__ import annotations

import datetime
import io
import re
import shutil
import time
import urllib.parse
import warnings
from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict
from unittest import mock

import autodict
import flask
import sqlalchemy

from nummus import portfolio, web
from nummus.models import (
    Account,
    AccountCategory,
    Asset,
    AssetCategory,
    Transaction,
    TransactionCategory,
    TransactionSplit,
)
from nummus.web_utils import HTTP_CODE_OK, HTTP_CODE_REDIRECT
from tests import TEST_LOG
from tests.base import TestBase

if TYPE_CHECKING:
    import werkzeug
    import werkzeug.datastructures


_RE_URI = re.compile(r"^[0-9a-f]{8}$")

ResultType = dict[str, object] | str | bytes
Tree = dict[str, "TreeNode"]
TreeNode = Tree | tuple[str, Tree] | object
Queries = dict[str, str] | dict[str, str | bool | list[str | bool]]


class PortfolioSetup(TypedDict):
    acct_id: int
    acct_uri: str
    acct_name: str

    txn_0_id: int
    txn_0_uri: str

    txn_1_id: int
    txn_1_uri: str

    t_split_0_id: int
    t_split_0_uri: str

    t_split_1_id: int
    t_split_1_uri: str

    payee_0: str
    payee_1: str

    tag_1: str

    cat_0_id: int
    cat_0_uri: str
    cat_0_name: str
    cat_0_emoji_name: str

    cat_1_id: int
    cat_1_uri: str
    cat_1_name: str
    cat_1_emoji_name: str

    asset_0_id: int
    asset_0_uri: str
    asset_0_name: str

    asset_1_id: int
    asset_1_uri: str
    asset_1_name: str


class WebTestBase(TestBase):
    def assertValidHTML(self, s: str) -> None:  # noqa: N802
        """Test HTML is valid based on tags.

        Args:
            s: String to test
        """
        tags: list[str] = re.findall(r"<(/?\w+)(?:[ \n][^<>]+)?>", s)

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

        # Find all DOM ids and validate no duplicates
        ids: list[str] = re.findall(r'id="([^"]+)"', s)
        id_counts: dict[str, int] = defaultdict(int)
        for e_id in ids:
            id_counts[e_id] += 1
        duplicates = {e_id for e_id, count in id_counts.items() if count != 1}
        self.assertEqual(duplicates, set(), "Duplicate element ids")

    def _setup_portfolio(self) -> PortfolioSetup:
        """Create accounts and transactions to test with.

        Returns:
            PortfolioSetup
        """
        self._clear_portfolio()
        p = self._portfolio

        today = datetime.date.today()

        acct_name = "Monkey Bank Checking"
        payee_0 = "Apple"
        payee_1 = "Banana"

        cat_0_name = "interest"
        cat_0_emoji_name = "😀 Interest"
        cat_1_name = "travel"
        cat_1_emoji_name = "Travel"

        tag_1 = self.random_string()

        asset_0_name = "Banana Inc."
        asset_1_name = "Fruit Ct. House"

        with p.begin_session() as s:
            acct = Account(
                name=acct_name,
                institution="Monkey Bank",
                category=AccountCategory.CASH,
                closed=False,
                budgeted=True,
            )
            s.add(acct)
            s.flush()
            acct_id = acct.id_
            acct_uri = acct.uri

            TransactionCategory.add_default(s)
            categories = TransactionCategory.map_name(s)
            # Reverse categories for LUT
            categories = {v: k for k, v in categories.items()}

            s.query(TransactionCategory).where(
                TransactionCategory.name == cat_0_name,
            ).update({"emoji_name": cat_0_emoji_name})

            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=100,
                statement=self.random_string(),
                payee=payee_0,
                cleared=False,
            )
            t_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories[cat_0_name],
            )
            s.add_all((txn, t_split))
            s.flush()

            txn_0_id = txn.id_
            txn_0_uri = txn.uri
            t_split_0_id = t_split.id_
            t_split_0_uri = t_split.uri

            txn = Transaction(
                account_id=acct.id_,
                date=today,
                amount=-10,
                statement=self.random_string(),
                payee=payee_1,
                cleared=True,
            )
            t_split = TransactionSplit(
                parent=txn,
                amount=txn.amount,
                category_id=categories[cat_1_name],
                tag=tag_1,
            )
            s.add_all((txn, t_split))
            s.flush()
            txn_1_id = txn.id_
            txn_1_uri = txn.uri
            t_split_1_id = t_split.id_
            t_split_1_uri = t_split.uri

            a_0 = Asset(name=asset_0_name, category=AssetCategory.ITEM)
            a_1 = Asset(name=asset_1_name, category=AssetCategory.REAL_ESTATE)

            s.add_all((a_0, a_1))
            s.flush()
            asset_0_id = a_0.id_
            asset_0_uri = a_0.uri
            asset_1_id = a_1.id_
            asset_1_uri = a_1.uri

        return {
            "acct_id": acct_id,
            "acct_uri": acct_uri,
            "acct_name": acct_name,
            "txn_0_id": txn_0_id,
            "txn_0_uri": txn_0_uri,
            "txn_1_id": txn_1_id,
            "txn_1_uri": txn_1_uri,
            "t_split_0_id": t_split_0_id,
            "t_split_0_uri": t_split_0_uri,
            "t_split_1_id": t_split_1_id,
            "t_split_1_uri": t_split_1_uri,
            "payee_0": payee_0,
            "payee_1": payee_1,
            "tag_1": tag_1,
            "cat_0_id": categories[cat_0_name],
            "cat_0_uri": TransactionCategory.id_to_uri(categories[cat_0_name]),
            "cat_0_name": cat_0_name,
            "cat_0_emoji_name": cat_0_emoji_name,
            "cat_1_id": categories[cat_1_name],
            "cat_1_uri": TransactionCategory.id_to_uri(categories[cat_1_name]),
            "cat_1_name": cat_1_name,
            "cat_1_emoji_name": cat_1_emoji_name,
            "asset_0_id": asset_0_id,
            "asset_0_uri": asset_0_uri,
            "asset_0_name": asset_0_name,
            "asset_1_id": asset_1_id,
            "asset_1_uri": asset_1_uri,
            "asset_1_name": asset_1_name,
        }

    def _clear_portfolio(self) -> None:
        """Clear all content from portfolio."""
        # Clean portfolio
        # In order of deletion, so children models first
        with self._portfolio.begin_session() as s:
            metadata = sqlalchemy.MetaData()
            metadata.reflect(bind=s.get_bind())
            for table in reversed(metadata.sorted_tables):
                s.query(table).delete()

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
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """Run a test HTTP request.

        Args:
            method: HTTP method to use
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        if isinstance(endpoint, str):
            url_args = {}
        else:
            endpoint, url_args = endpoint
        with self._flask_app.app_context(), self._flask_app.test_request_context():
            url = flask.url_for(
                endpoint,
                _anchor=None,
                _method=None,
                _scheme=None,
                _external=False,
                **url_args,
            )
            clean_args = {
                k: (
                    "<values>"
                    if isinstance(v, list)
                    else (
                        "{uri}"
                        if isinstance(v, str) and _RE_URI.match(v)
                        else "<value>"
                    )
                )
                for k, v in url_args.items()
            }
            clean_url = urllib.parse.unquote(
                flask.url_for(
                    endpoint,
                    _anchor=None,
                    _method=None,
                    _scheme=None,
                    _external=False,
                    **clean_args,
                ),
            )

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
            self.assertEqual(response.status_code, rc)
            self.assertEqual(response.content_type, content_type)

            with autodict.JSONAutoDict(str(TEST_LOG)) as d:
                if clean_url not in d["web_latency"]:
                    d["web_latency"][clean_url] = []
                d["web_latency"][clean_url].append(duration)

            if content_type == "text/html; charset=utf-8":
                html = response.text
                if response.status_code != HTTP_CODE_REDIRECT:
                    # werkzeug redirect doesn't have close tags
                    self.assertValidHTML(html)
                # Remove whitespace
                html = "".join(html.split("\n"))
                html = re.sub(r" +", " ", html)
                html = re.sub(r" ?> ?", ">", html)
                html = re.sub(r" ?< ?", "<", html)
                return html, response.headers
            return response.data, response.headers
        finally:
            if response is not None:
                response.close()

    def web_get(
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """Run a test HTTP GET request.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "GET",
            endpoint,
            rc=rc,
            content_type=content_type,
            **kwargs,
        )

    def web_put(
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """Run a test HTTP PUT request.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "PUT",
            endpoint,
            rc=rc,
            content_type=content_type,
            **kwargs,
        )

    def web_post(
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """Run a test HTTP POST request.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "POST",
            endpoint,
            rc=rc,
            content_type=content_type,
            **kwargs,
        )

    def web_delete(
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """Run a test HTTP DELETE request.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.web_open(
            "DELETE",
            endpoint,
            rc=rc,
            content_type=content_type,
            **kwargs,
        )
