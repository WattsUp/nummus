"""Test module nummus.web.controller_config
"""

import warnings

from nummus import portfolio, __version__

from tests.base import TestBase


class TestControllerConfig(TestBase):
  """Test controller_config methods
  """

  def test_get_version(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)
    client = self._get_api_client(p)

    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      response = client.get("/api/version")
    self.assertEqual(200, response.status_code)
    self.assertEqual("application/json", response.content_type)

    result = response.json
    target = {"api": "0.1.0", "nummus": __version__}
    self.assertDictEqual(target, result)
