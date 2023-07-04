"""Test module nummus.web.controller_html
"""

from tests.web.base import WebTestBase


class TestControllerHTML(WebTestBase):
  """Test controller_html methods
  """

  def test_get_home(self):
    endpoint = "/"
    result, _ = self.api_get(endpoint, content_type="text/html; charset=utf-8")
    self.assertIn("Hello World page", result)
