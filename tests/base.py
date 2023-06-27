"""Test base class
"""

import pathlib
import shutil
import string
import time
import unittest
import uuid
import warnings

import autodict
import connexion
import flask
import flask.testing
import numpy as np
from sqlalchemy import orm, pool

from nummus import sql, portfolio, web

from tests import TEST_LOG


class TestBase(unittest.TestCase):
  """Test base class
  """

  _TEST_ROOT = pathlib.Path(".test")
  _DATA_ROOT = pathlib.Path(__file__).parent.joinpath("data")
  _P_FAIL = 1e-4
  _RNG = np.random.default_rng()

  @classmethod
  def random_string(cls, length: int = 20) -> str:
    """Generate a random string a-zA-Z

    Args:
      length: Length of string to generate

    Returns:
      Random string
    """
    return "".join(list(cls._RNG.choice(list(string.ascii_letters), length)))

  def _get_session(self) -> orm.Session:
    """Obtain a test sql session
    """
    config = autodict.AutoDict(encrypt=False)
    path = self._TEST_ROOT.joinpath(f"{uuid.uuid4()}.db")
    return sql.get_session(path, config)

  def _get_api_client(self,
                      p: portfolio.Portfolio) -> flask.testing.FlaskClient:
    """Get test API client for a Portfolio

    Args:
      p: Portfolio to serve

    Returns:
      Flask test client
    """
    s = web.Server(p, "127.0.0.1", 8080, False)
    s_server = s._server  # pylint: disable=protected-access
    connexion_app: connexion.FlaskApp = s_server.application
    flask_app: flask.Flask = connexion_app.app
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      return flask_app.test_client()

  def _clean_test_root(self):
    """Clean root test folder
    """
    if self._TEST_ROOT.exists():
      shutil.rmtree(self._TEST_ROOT)

  def assertEqualWithinError(self, target, real, threshold):
    """Assert if target != real within threshold

    Args:
      target: Target value
      real: Test value
      threshold: Fractional amount real can be off
    """
    if target == 0.0:
      error = np.abs(real - target)
    else:
      error = np.abs(real / target - 1)
    self.assertLessEqual(error, threshold)

  def setUp(self):
    sql.drop_session()
    self._clean_test_root()
    self._TEST_ROOT.mkdir(parents=True, exist_ok=True)
    self._test_start = time.perf_counter()

    # Remove sleeping by default, mainly in read hardware interaction
    self._original_sleep = time.sleep
    time.sleep = lambda *args: None

    # Change all engines to NullPool so timing isn't an issue
    sql._ENGINE_ARGS["poolclass"] = pool.NullPool  # pylint: disable=protected-access

  def tearDown(self):
    sql.drop_session()
    duration = time.perf_counter() - self._test_start
    with autodict.JSONAutoDict(TEST_LOG) as d:
      d["methods"][self.id()] = duration
    self._clean_test_root()

    # Restore sleeping
    time.sleep = self._original_sleep

  def log_speed(self, slow_duration: float, fast_duration: float):
    """Log the duration of a slow/fast A/B comparison test

    Args:
      slow_duration: Duration of slow test
      fast_duration: Duration of fast test
    """
    with autodict.JSONAutoDict(TEST_LOG) as d:
      d["speed"][self.id()] = {
          "slow": slow_duration,
          "fast": fast_duration,
          "increase": slow_duration / fast_duration
      }

  @classmethod
  def setUpClass(cls):
    print(f"{cls.__module__}.{cls.__qualname__}[", end="", flush=True)
    cls._CLASS_START = time.perf_counter()

  @classmethod
  def tearDownClass(cls):
    print("]done", flush=True)
    # time.sleep(10)
    duration = time.perf_counter() - cls._CLASS_START
    with autodict.JSONAutoDict(TEST_LOG) as d:
      d["classes"][f"{cls.__module__}.{cls.__qualname__}"] = duration
