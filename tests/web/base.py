"""TestBase with extra functions for web testing
"""

from typing import Callable, Dict, Tuple, Union

import io
import re
import time
from unittest import mock
import urllib.parse
import warnings

import autodict
import connexion
import flask
import flask.testing
import werkzeug

from nummus import portfolio, sql, web
from nummus.models import (Account, AssetValuation, Asset, Budget, Credentials,
                           Transaction, TransactionSplit)

from tests import TEST_LOG
from tests.base import TestBase

_RE_UUID = re.compile(r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-"
                      r"[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}")

ResultType = Union[Dict[str, object], str, bytes]
HeadersType = Dict[str, str]


class WebTestBase(TestBase):
  """TestBase with extra functions for web testing
  """

  @classmethod
  def setUpClass(cls):
    super().setUpClass()
    cls._clean_test_root()

    # Create a portfolio for the test class
    path_db = cls._TEST_ROOT.joinpath("portfolio.db")
    cls._portfolio = portfolio.Portfolio.create(path_db, None)

    s = web.Server(cls._portfolio, "127.0.0.1", 8080, False)
    s_server = s._server  # pylint: disable=protected-access
    connexion_app: connexion.FlaskApp = s_server.application
    flask_app: flask.Flask = connexion_app.app
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      cls._client = flask_app.test_client()

  @classmethod
  def tearDownClass(cls):
    cls._client = None
    cls._portfolio = None
    sql.drop_session()
    cls._clean_test_root()
    super().tearDownClass()

  def setUp(self):
    super().setUp(clean=False)

  def tearDown(self):
    # Clean portfolio
    # In order of deletion, so children models first
    models = [
        AssetValuation, Budget, Credentials, TransactionSplit, Transaction,
        Asset, Account
    ]
    with self._portfolio.get_session() as s:
      for model in models:
        for instance in s.query(model).all():
          s.delete(instance)
        s.commit()

    super().tearDown(clean=False)

  def assertHTTPRaises(self, rc: int, func: Callable, *args, **kwargs) -> None:
    """Test function raises ProblemException with the matching HTTP return code

    Args:
      rc: HTTP code to match
      func: Callable to test
      All other arguments passed to func()
    """
    with self.assertRaises(connexion.exceptions.ProblemException) as cm:
      func(*args, **kwargs)
    e: connexion.exceptions.ProblemException = cm.exception
    self.assertEqual(rc, e.status)

  def api_open(self,
               method: str,
               endpoint: str,
               queries: Dict[str, str],
               content_type: str = "application/json",
               rc: int = 200,
               **kwargs) -> Tuple[ResultType, HeadersType]:
    """Run a test API GET

    Args:
      client: Test client from get_api_client
      method: HTTP method to use
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc in [200, 201]
      rc: Expected HTTP return code
      All other arguments passed to client.get

    Returns:
      (response.json, headers) if content_type == application/json
      (response.text, headers) if content_type == text/html
      (response.get_data(), headers) otherwise
    """
    if rc == 204:
      content_type = None
    if queries is None or len(queries) < 1:
      url = endpoint
    else:
      queries_flat = [
          f"{k}={urllib.parse.quote(str(v))}" for k, v in queries.items()
      ]
      url = f"{endpoint}?{'&'.join(queries_flat)}"

    kwargs["method"] = method
    response: werkzeug.test.TestResponse = None
    try:
      with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        start = time.perf_counter()
        if rc in [200, 201]:
          response = self._client.open(url, **kwargs)
        else:
          with mock.patch("sys.stderr", new=io.StringIO()) as _:
            response = self._client.open(url, **kwargs)
      duration = time.perf_counter() - start
      self.assertEqual(rc, response.status_code, msg=response.text)
      if rc in [200, 201]:
        self.assertEqual(content_type, response.content_type)
      if rc == 201:
        self.assertIn("Location", response.headers)
      if rc == 204:
        self.assertEqual(b"", response.get_data())

      with autodict.JSONAutoDict(TEST_LOG) as d:
        # Replace uuid with <uuid>
        endpoint = _RE_UUID.sub("<uuid>", endpoint)
        k = f"{method:6} {endpoint}"
        if queries is not None and len(queries) >= 1:
          queries_flat = [f"{k}=<value>" for k in queries]
          k += f"?{'&'.join(queries_flat)}"
        if k not in d["api_latency"]:
          d["api_latency"][k] = []
        d["api_latency"][k].append(duration)
      self.assertLessEqual(duration, 0.15)  # All responses faster than 150ms

      if content_type is None:
        return response.get_data(), response.headers
      if content_type == "application/json":
        return response.json, response.headers
      if content_type.startswith("text/html"):
        return response.text, response.headers
      return response.get_data(), response.headers
    finally:
      if response is not None:
        response.close()

  def api_get(self,
              endpoint: str,
              queries: Dict[str, str] = None,
              content_type: str = "application/json",
              rc: int = 200,
              **kwargs) -> Tuple[ResultType, HeadersType]:
    """Run a test API GET

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc in [200, 201]
      rc: Expected return code, default for GET is 200 OK
      All other arguments passed to client.get

    Returns:
      (response.json, headers) if content_type == application/json
      (response.text, headers) if content_type == text/html
      (response.get_data(), headers) otherwise
    """
    return self.api_open("GET",
                         endpoint,
                         queries,
                         content_type=content_type,
                         rc=rc,
                         **kwargs)

  def api_put(self,
              endpoint: str,
              queries: Dict[str, str] = None,
              content_type: str = "application/json",
              rc: int = 200,
              **kwargs) -> Tuple[ResultType, HeadersType]:
    """Run a test API PUT

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc in [200, 201]
      rc: Expected return code, default for PUT is 200 OK
      All other arguments passed to client.get

    Returns:
      (response.json, headers) if content_type == application/json
      (response.text, headers) if content_type == text/html
      (response.get_data(), headers) otherwise
    """
    return self.api_open("PUT",
                         endpoint,
                         queries,
                         content_type=content_type,
                         rc=rc,
                         **kwargs)

  #

  def api_post(self,
               endpoint: str,
               queries: Dict[str, str] = None,
               content_type: str = "application/json",
               rc: int = 201,
               **kwargs) -> Tuple[ResultType, HeadersType]:
    """Run a test API POST

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc in [200, 201]
      rc: Expected return code, default for POST is 201 Created
      All other arguments passed to client.get

    Returns:
      (response.json, headers) if content_type == application/json
      (response.text, headers) if content_type == text/html
      (response.get_data(), headers) otherwise
    """
    return self.api_open("POST",
                         endpoint,
                         queries,
                         content_type=content_type,
                         rc=rc,
                         **kwargs)

  def api_delete(self,
                 endpoint: str,
                 queries: Dict[str, str] = None,
                 content_type: str = None,
                 rc: int = 204,
                 **kwargs) -> Tuple[ResultType, HeadersType]:
    """Run a test API DELETE

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc in [200, 201]
      rc: Expected return code, default for DELETE is 204 No Content
      All other arguments passed to client.get

    Returns:
      (response.json, headers) if content_type == application/json
      (response.text, headers) if content_type == text/html
      (response.get_data(), headers) otherwise
    """
    return self.api_open("DELETE",
                         endpoint,
                         queries,
                         content_type=content_type,
                         rc=rc,
                         **kwargs)
