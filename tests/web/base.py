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

from nummus import portfolio, web

from tests import TEST_LOG
from tests.base import TestBase

_RE_UUID = re.compile(r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-"
                      r"[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}")


class WebTestBase(TestBase):
  """TestBase with extra functions for web testing
  """

  def setUp(self):
    super().setUp()

    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    self._portfolio = portfolio.Portfolio.create(path_db, None)

    s = web.Server(self._portfolio, "127.0.0.1", 8080, False)
    s_server = s._server  # pylint: disable=protected-access
    connexion_app: connexion.FlaskApp = s_server.application
    flask_app: flask.Flask = connexion_app.app
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      self._client = flask_app.test_client()

  def tearDown(self):
    self._client = None
    self._portfolio = None

    super().tearDown()

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
