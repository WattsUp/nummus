"""Test module nummus.web.controller_config
"""

from nummus import __version__

from tests.web.base import WebTestBase


class TestControllerConfig(WebTestBase):
  """Test controller_config methods
  """

  def test_get_version(self):
    result = self.api_get("/api/version",)
    target = {"api": "0.1.0", "nummus": __version__}
    self.assertDictEqual(target, result)
