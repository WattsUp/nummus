"""Test module nummus.controllers.dashboard
"""

from tests.controllers.base import WebTestBase


class TestDashboard(WebTestBase):
  """Test dashboard controller
  """

  def test_page_home(self):
    endpoint = "/"
    result, _ = self.api_get(endpoint, content_type="text/html; charset=utf-8")
    target = '<!DOCTYPE html>\n<html lang="en">'
    self.assertEqual(target, result[:len(target)])
    target = "</html>"
    self.assertEqual(target, result[-len(target):])
    self.assertValidHTML(result)
