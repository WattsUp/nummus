"""Test module nummus.web.server
"""

import io
from unittest import mock

from colorama import Fore
import connexion
import flask

from nummus import portfolio
from nummus.web import server

from tests.base import TestBase


class TestServer(TestBase):
  """Test Server class
  """

  def test_init_properties(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)

    host = "127.0.0.1"
    port = 80
    enable_api_ui = True

    s = server.Server(p, host, port, enable_api_ui)
    self.assertEqual(p, s._portfolio)  # pylint: disable=protected-access
    self.assertEqual(enable_api_ui, s._enable_api_ui)  # pylint: disable=protected-access

    s_server = s._server  # pylint: disable=protected-access
    connexion_app: connexion.FlaskApp = s_server.application
    flask_app: flask.Flask = connexion_app.app

    with flask_app.app_context():
      flask_p: portfolio.Portfolio = flask.current_app.portfolio
    self.assertEqual(p, flask_p)

    self.assertEqual(enable_api_ui,
                     connexion_app.options.as_dict()["swagger_ui"])
    self.assertEqual(host, s_server.server_host)
    self.assertEqual(port, s_server.server_port)

    enable_api_ui = False
    s = server.Server(p, host, port, enable_api_ui)
    self.assertEqual(enable_api_ui, s._enable_api_ui)  # pylint: disable=protected-access

    s_server = s._server  # pylint: disable=protected-access
    connexion_app: connexion.FlaskApp = s_server.application
    self.assertEqual(enable_api_ui,
                     connexion_app.options.as_dict()["swagger_ui"])

  def test_run(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)

    host = "127.0.0.1"
    port = 8080
    enable_api_ui = True
    s = server.Server(p, host, port, enable_api_ui)
    s_server = s._server  # pylint: disable=protected-access

    s_server.serve_forever = lambda *_: print("serve_forever")
    s_server.stop = lambda *_: print("stop")

    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      s.run()

    fake_stdout = fake_stdout.getvalue()
    url = f"http://{host}:{port}"
    target = (f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
              f"{Fore.CYAN}nummus API UI running on {url}/api/ui\n"
              "serve_forever\n"
              f"{Fore.YELLOW}nummus web shutdown at ")  # skip timestamp
    self.assertEqual(target, fake_stdout[:len(target)])

    enable_api_ui = False
    s = server.Server(p, host, port, enable_api_ui)
    s_server = s._server  # pylint: disable=protected-access

    def raise_keyboard_interrupt():
      raise KeyboardInterrupt

    s_server.serve_forever = raise_keyboard_interrupt
    s_server.stop = lambda *_: print("stop")

    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      s.run()

    fake_stdout = fake_stdout.getvalue()
    url = f"http://{host}:{port}"
    target = (f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
              f"{Fore.YELLOW}Shutting down on interrupt\n"
              f"{Fore.YELLOW}nummus web shutdown at ")  # skip timestamp
    self.assertEqual(target, fake_stdout[:len(target)])

    # Artificially set started=True
    s_server._stop_event.clear()  # pylint: disable=protected-access
    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      s.run()

    fake_stdout = fake_stdout.getvalue()
    url = f"http://{host}:{port}"
    target = (f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
              f"{Fore.YELLOW}Shutting down on interrupt\n"
              "stop\n"
              f"{Fore.YELLOW}nummus web shutdown at ")  # skip timestamp
    self.assertEqual(target, fake_stdout[:len(target)])
