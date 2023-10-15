import io
import re
import shutil
import time
import urllib.parse
import warnings
from unittest import mock

import autodict
import flask
import flask.testing
import werkzeug

from nummus import custom_types as t
from nummus import portfolio, sql, web
from nummus.models import (
    Account,
    Asset,
    AssetValuation,
    Budget,
    Credentials,
    Transaction,
    TransactionSplit,
)
from tests import TEST_LOG
from tests.base import TestBase

_RE_UUID = re.compile(
    r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-"
    r"[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}"
)

ResultType = t.Union[t.DictAny, str, bytes]
CovMethods = t.Dict[t.Union[int, str], bool]


class WebTestBase(TestBase):
    def assertValidHTML(self, s: str) -> None:  # noqa: N802
        """Test HTML is valid based on tags.

        Args:
            s: String to test
        """
        tags: t.Strings = re.findall(r"<(/?\w+)(?: [^<>]+)?>", s)
        tree: t.DictAny = {"__parent__": (None, None)}
        current_node = tree
        for tag in tags:
            if tag[0] == "/":
                # Close tag
                current_tag, parent = current_node.pop("__parent__")
                current_node = parent
                self.assertEqual(current_tag, tag[1:])
            elif tag in ["link", "meta", "path", "input", "hr"]:
                # Tags without close tags
                current_node[tag] = {}
            else:
                current_node[tag] = {"__parent__": (tag, current_node)}
                current_node = current_node[tag]

        # Got back up to the root element
        tag, parent = current_node.pop("__parent__")
        self.assertIn(tag, [None, "html"])  # <html> might not be closed
        if parent is not None:
            parent: t.DictAny
            self.assertEqual({"__parent__", "html"}, parent.keys())

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

        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                # Ignore SSL warnings
                s = web.Server(cls._portfolio, "127.0.0.1", 8080, False)
        cls._flask_app: flask.Flask = s._app  # pylint: disable=protected-access
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cls._client = cls._flask_app.test_client()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._client = None
        cls._portfolio = None
        sql.drop_session()
        cls._clean_test_root()
        super().tearDownClass()

    def setUp(self) -> None:
        self._original_render_template = flask.render_template

        self._called_context: t.DictAny = {}

        def render_template(path: str, **context: t.DictAny) -> str:
            self._called_context.clear()
            self._called_context.update(**context)
            return self._original_render_template(path, **context)

        flask.render_template = render_template

        super().setUp(clean=False)

    def tearDown(self) -> None:
        flask.render_template = self._original_render_template

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

        super().tearDown(clean=False)

    def web_open(
        self,
        method: str,
        endpoint: str,
        queries: t.DictStr = None,
        content_type: str = "text/html; charset=utf-8",
        rc: int = 200,
        **kwargs: t.Any,
    ) -> t.Tuple[ResultType, t.DictStr]:
        """Run a test HTTP request.

        Args:
            method: HTTP method to use
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            content_type: Expected content type
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers) if content_type == text/html
            (response.get_data(), headers) otherwise
        """
        if queries is None or len(queries) < 1:
            url = endpoint
        else:
            queries_flat = []
            for k, v in queries.items():
                if isinstance(v, str):
                    v = [v]
                queries_flat.extend(f"{k}={urllib.parse.quote(str(vv))}" for vv in v)
            url = f"{endpoint}?{'&'.join(queries_flat)}"

        kwargs["method"] = method
        response: werkzeug.test.TestResponse = None
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                start = time.perf_counter()
                if rc == 200:
                    response = self._client.open(url, **kwargs)
                else:
                    with mock.patch("sys.stderr", new=io.StringIO()) as _:
                        response = self._client.open(url, **kwargs)
            duration = time.perf_counter() - start
            self.assertEqual(rc, response.status_code, msg=response.text)
            self.assertEqual(content_type, response.content_type)

            with autodict.JSONAutoDict(TEST_LOG) as d:
                # Replace uuid with {accountUUID, assetUUID, ...}
                parts = []
                for p in endpoint.split("/"):
                    if _RE_UUID.match(p):
                        if "account" in parts[-1]:
                            parts.append("{accountUUID}")
                        elif "asset" in parts[-1]:
                            parts.append("{assetUUID}")
                        elif "budget" in parts[-1]:
                            parts.append("{budgetUUID}")
                        elif "transaction" in parts[-1]:
                            parts.append("{transactionUUID}")
                        else:
                            parts.append("{uuid}")
                    else:
                        parts.append(p)
                endpoint = "/".join(parts)
                k = f"{method:6} {endpoint}"
                if queries is not None and len(queries) >= 1:
                    queries_flat = [f"{k}=<value>" for k in queries]
                    k += f"?{'&'.join(queries_flat)}"
                if k not in d["web_latency"]:
                    d["web_latency"][k] = []
                d["web_latency"][k].append(duration)

            self.assertLessEqual(duration, 0.2)  # All responses faster than 200ms

            if content_type is None:
                return response.get_data(), response.headers
            if content_type.startswith("text/html"):
                html = response.text
                self.assertValidHTML(html)
                return html, response.headers
            return response.get_data(), response.headers
        finally:
            if response is not None:
                response.close()

    def web_get(
        self,
        endpoint: str,
        queries: t.DictStr = None,
        content_type: str = "text/html; charset=utf-8",
        rc: int = 200,
        **kwargs: t.Any,
    ) -> t.Tuple[ResultType, t.DictStr]:
        """Run a test HTTP GET request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            content_type: Expected content type
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers) if content_type == text/html
            (response.get_data(), headers) otherwise
        """
        return self.web_open(
            "GET",
            endpoint,
            queries,
            content_type=content_type,
            rc=rc,
            **kwargs,
        )

    def web_put(
        self,
        endpoint: str,
        queries: t.DictStr = None,
        content_type: str = "text/html; charset=utf-8",
        rc: int = 200,
        **kwargs: t.Any,
    ) -> t.Tuple[ResultType, t.DictStr]:
        """Run a test HTTP PUT request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            content_type: Expected content type
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers) if content_type == text/html
            (response.get_data(), headers) otherwise
        """
        return self.web_open(
            "PUT",
            endpoint,
            queries,
            content_type=content_type,
            rc=rc,
            **kwargs,
        )

    def web_post(
        self,
        endpoint: str,
        queries: t.DictStr = None,
        content_type: str = "text/html; charset=utf-8",
        rc: int = 200,
        **kwargs: t.Any,
    ) -> t.Tuple[ResultType, t.DictStr]:
        """Run a test HTTP POST request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            content_type: Expected content type
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers) if content_type == text/html
            (response.get_data(), headers) otherwise
        """
        return self.web_open(
            "POST",
            endpoint,
            queries,
            content_type=content_type,
            rc=rc,
            **kwargs,
        )

    def web_delete(
        self,
        endpoint: str,
        queries: t.DictStr = None,
        content_type: str = "text/html; charset=utf-8",
        rc: int = 200,
        **kwargs: t.Any,
    ) -> t.Tuple[ResultType, t.DictStr]:
        """Run a test HTTP DELETE request.

        Args:
            endpoint: URL endpoint to test
            queries: Dictionary of queries to append, will run through
            urllib.parse.quote
            content_type: Expected content type
            rc: Expected HTTP return code
            kwargs: Passed to client.get

        Returns:
            (response.text, headers) if content_type == text/html
            (response.get_data(), headers) otherwise
        """
        return self.web_open(
            "DELETE",
            endpoint,
            queries,
            content_type=content_type,
            rc=rc,
            **kwargs,
        )
