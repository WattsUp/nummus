"""TestBase with extra functions for web testing
"""

from typing import Dict, Union

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

  def api_open(self,
               method: str,
               endpoint: str,
               queries: Dict[str, str],
               content_type: str = "application/json",
               rc: int = 200,
               **kwargs) -> Union[Dict[str, object], str, bytes]:
    """Run a test API GET

    Args:
      client: Test client from get_api_client
      method: HTTP method to use
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc == 200
      rc: Expected HTTP return code
      All other arguments passed to client.get

    Returns:
      response.json if content_type == application/json
      response.text if content_type == text/html
      response.get_data() otherwise
    """
    if queries is None or len(queries) < 1:
      url = endpoint
    else:
      queries_flat = [
          f"{k}={urllib.parse.quote(str(v))}" for k, v in queries.items()
      ]
      url = f"{endpoint}?{'&'.join(queries_flat)}"

    kwargs["method"] = method
    response: werkzeug.Response = None
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
      if rc == 200:
        self.assertEqual(content_type, response.content_type)
      self.assertLessEqual(duration, 0.1)  # All responses faster than 100ms

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

      if content_type == "application/json":
        return response.json
      if content_type.startswith("text/html"):
        return response.text
      return response.get_data()
    finally:
      if response is not None:
        response.close()

  def api_get(self,
              endpoint: str,
              queries: Dict[str, str] = None,
              content_type: str = "application/json",
              rc: int = 200,
              **kwargs) -> Union[Dict[str, object], str, bytes]:
    """Run a test API GET

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc == 200
      rc: Expected return code
      All other arguments passed to client.get

    Returns:
      response.json if content_type == application/json
      response.text if content_type == text/html
      response.get_data() otherwise
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
              **kwargs) -> Union[Dict[str, object], str, bytes]:
    """Run a test API PUT

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc == 200
      rc: Expected return code
      All other arguments passed to client.get

    Returns:
      response.json if content_type == application/json
      response.text if content_type == text/html
      response.get_data() otherwise
    """
    return self.api_open("PUT",
                         endpoint,
                         queries,
                         content_type=content_type,
                         rc=rc,
                         **kwargs)

  def api_post(self,
               endpoint: str,
               queries: Dict[str, str] = None,
               content_type: str = "application/json",
               rc: int = 200,
               **kwargs) -> Union[Dict[str, object], str, bytes]:
    """Run a test API POST

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc == 200
      rc: Expected return code
      All other arguments passed to client.get

    Returns:
      response.json if content_type == application/json
      response.text if content_type == text/html
      response.get_data() otherwise
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
                 content_type: str = "application/json",
                 rc: int = 200,
                 **kwargs) -> Union[Dict[str, object], str, bytes]:
    """Run a test API DELETE

    Args:
      endpoint: URL endpoint to test
      queries: Dictionary of queries to append, will run through
        urllib.parse.quote
      content_type: Expected content type if rc == 200
      rc: Expected return code
      All other arguments passed to client.get

    Returns:
      response.json if content_type == application/json
      response.text if content_type == text/html
      response.get_data() otherwise
    """
    return self.api_open("DELETE",
                         endpoint,
                         queries,
                         content_type=content_type,
                         rc=rc,
                         **kwargs)
