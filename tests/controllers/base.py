"""TestBase with extra functions for web testing
"""

import io
import re
import shutil
import time
from unittest import mock
import urllib.parse
import warnings

import autodict
import flask
import flask.testing
import werkzeug

from nummus import portfolio, sql, web
from nummus import custom_types as t
from nummus.models import (Account, AssetValuation, Asset, Budget, Credentials,
                           Transaction, TransactionSplit)

from tests import TEST_LOG
from tests.base import TestBase

_RE_UUID = re.compile(r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-"
                      r"[0-9a-fA-F]{4}\b-[0-9a-fA-F]{12}")

ResultType = t.Union[t.DictAny, str, bytes]
CovMethods = t.Dict[t.Union[int, str], bool]


class WebTestBase(TestBase):
  """TestBase with extra functions for web testing
  """

  def assertValidHTML(self, s: str):
    """Test HTML is valid based on tags

    Args:
      s: String to test
    """
    tags: t.Strings = re.findall(r"<(/?\w+)(?: [^<>]+)?>", s)
    DOMTree = t.Dict[str, "DOMTree"]
    tree: DOMTree = {"__parent__": (None, None)}
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
    self.assertEqual(tag, None)
    self.assertEqual(parent, None)

  @classmethod
  def setUpClass(cls):
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
  def tearDownClass(cls):
    cls._client = None
    cls._portfolio = None
    sql.drop_session()
    cls._clean_test_root()
    super().tearDownClass()

  def setUp(self):
    self._original_render_template = flask.render_template

    self._called_context: t.DictAny = {}

    def render_template(path: str, **context: t.DictAny) -> str:
      self._called_context.clear()
      self._called_context.update(**context)
      return self._original_render_template(path, **context)

    flask.render_template = render_template

    super().setUp(clean=False)

  def tearDown(self):
    flask.render_template = self._original_render_template

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
               queries: t.DictStr,
               content_type: str = "application/json",
               rc: int = 200,
               **kwargs) -> t.Tuple[ResultType, t.DictStr]:
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
      queries_flat = []
      for k, v in queries.items():
        if isinstance(v, list):
          queries_flat.extend(f"{k}={urllib.parse.quote(str(vv))}" for vv in v)
        else:
          queries_flat.append(f"{k}={urllib.parse.quote(str(v))}")
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
        if k not in d["api_latency"]:
          d["api_latency"][k] = []
        d["api_latency"][k].append(duration)

        # Add to api_coverage
        if endpoint.startswith("/api"):
          if method not in d["api_coverage"][endpoint]:
            d["api_coverage"][endpoint][method] = []
          d["api_coverage"][endpoint][method].append(response.status_code)
          if queries is not None and len(queries) >= 1:
            for k in queries:
              d["api_coverage"][endpoint][method].append(k)
          else:
            d["api_coverage"][endpoint][method].append(None)

      self.assertLessEqual(duration, 0.2)  # All responses faster than 200ms

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
              queries: t.DictStr = None,
              content_type: str = "application/json",
              rc: int = 200,
              **kwargs) -> t.Tuple[ResultType, t.DictStr]:
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
              queries: t.DictStr = None,
              content_type: str = "application/json",
              rc: int = 200,
              **kwargs) -> t.Tuple[ResultType, t.DictStr]:
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

  def api_post(self,
               endpoint: str,
               queries: t.DictStr = None,
               content_type: str = "application/json",
               rc: int = 200,
               **kwargs) -> t.Tuple[ResultType, t.DictStr]:
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
                 queries: t.DictStr = None,
                 content_type: str = None,
                 rc: int = 200,
                 **kwargs) -> t.Tuple[ResultType, t.DictStr]:
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


def api_coverage() -> t.Dict[str, t.Dict[str, CovMethods]]:
  """Get API Coverage results

  Returns:
    {endpoint: {method: {permutations: covered bool}}}
  """
  # Initialize data from api.yaml with all False
  d: t.Dict[str, t.Dict[str, CovMethods]] = {}

  # Iterate through test log
  with autodict.JSONAutoDict(TEST_LOG) as log:
    LogYaml = t.Dict[str, t.DictStrings]
    d_log: LogYaml = log["api_coverage"]

  for endpoint, data in d_log.items():
    for method, branches in data.items():
      for branch in branches:
        if branch not in d[endpoint][method]:
          raise KeyError(f"API call not in spec: {method} {endpoint} {branch}")
        d[endpoint][method][branch] = True

  # List of endpoints and methods to remove from coverage
  no_cover: t.List[t.Tuple[str, str]] = []
  for endpoint, method in no_cover:
    # Remove misses
    d[endpoint][method] = {k: v for k, v in d[endpoint][method].items() if v}

  return d
