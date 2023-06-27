"""Test module nummus.web.controller_html
"""

import warnings

from nummus import portfolio

from tests.base import TestBase


class TestControllerHTML(TestBase):
  """Test controller_html methods
  """

  def test_get_home(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/")
    self.assertEqual(200, response.status_code)
    self.assertEqual("text/html; charset=utf-8", response.content_type)
    self.assertIn("Hello World page", response.text)
