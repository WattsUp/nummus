"""Test module nummus.web.controller_html
"""

from tests.web.base import WebTestBase


class TestControllerHTML(WebTestBase):
  """Test controller_html methods
  """

  def test_get_home(self):
    response = self.api_get("/")
    self.assertEqual("text/html; charset=utf-8", response.content_type)
    self.assertIn("Hello World page", response.text)
