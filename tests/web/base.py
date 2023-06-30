"""TestBase with extra functions for web testing
"""

import io
import re
import time
from unittest import mock
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
               rc: int = 200,
               **kwargs) -> werkzeug.Response:
    """Run a test API GET

    Args:
      client: Test client from get_api_client
      method: HTTP method to use
      endpoint: URL endpoint to test
      rc: Expected HTTP return code
      All other arguments passed to client.get
    """
    kwargs["method"] = method
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      start = time.perf_counter()
      if rc == 200:
        response = self._client.open(endpoint, **kwargs)
      else:
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
          response = self._client.open(endpoint, **kwargs)
      duration = time.perf_counter() - start
      self.assertEqual(rc, response.status_code)
      self.assertLessEqual(duration, 0.1)  # All responses faster than 100ms
      with autodict.JSONAutoDict(TEST_LOG) as d:
        # Replace uuid with <uuid>
        endpoint = _RE_UUID.sub("<uuid>", endpoint)
        k = f"{method} {endpoint}"
        if k not in d["api_latency"]:
          d["api_latency"][k] = []
        d["api_latency"][k].append(duration)
    return response

  def api_get(self, endpoint: str, **kwargs) -> werkzeug.Response:
    """Run a test API GET

    Args:
      endpoint: URL endpoint to test
      All other arguments passed to client.get
    """
    return self.api_open("GET", endpoint, **kwargs)

  def api_put(self, endpoint: str, **kwargs) -> werkzeug.Response:
    """Run a test API PUT

    Args:
      endpoint: URL endpoint to test
      All other arguments passed to client.get
    """
    return self.api_open("PUT", endpoint, **kwargs)

  def api_post(self,
               endpoint: str,
               rc: int = 200,
               **kwargs) -> werkzeug.Response:
    """Run a test API POST

    Args:
      endpoint: URL endpoint to test
      rc: Expected return code
      All other arguments passed to client.get
    """
    return self.api_open("POST", endpoint, rc, **kwargs)

  def api_delete(self, endpoint: str, **kwargs) -> werkzeug.Response:
    """Run a test API GET

    Args:
      endpoint: URL endpoint to test
      All other arguments passed to client.get
    """
    return self.api_open("DELETE", endpoint, **kwargs)
