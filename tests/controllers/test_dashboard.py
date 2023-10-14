"""Test module nummus.controllers.dashboard
"""

from tests.controllers.base import WebTestBase


class TestDashboard(WebTestBase):
  """Test dashboard controller
  """

  def test_page_home(self):
    endpoint = "/"
    result, _ = self.web_get(endpoint)
    target = '<!DOCTYPE html>\n<html lang="en">'
    self.assertEqual(target, result[:len(target)])
    target = "</html>"
    self.assertEqual(target, result[-len(target):])
