"""Test module nummus.web.server
"""

import io
import shutil
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

    with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        s = server.Server(p, host, port, enable_api_ui)
    fake_stderr = fake_stderr.getvalue()
    target = (f"{Fore.RED}No SSL certificate found at {p.ssl_cert_path}\n"
              f"{Fore.YELLOW}SSL certificate appears to be self-signed at "
              f"{p.ssl_cert_path}\n"
              "Replace with real certificate to disable this warning\n")
    self.assertEqual(target, fake_stderr)
    fake_stdout = fake_stdout.getvalue()
    target = (f"{Fore.MAGENTA}Generating self-signed certificate\n"
              "Please install certificate in web browser\n")
    self.assertEqual(target, fake_stdout)

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

    # Copy not self-signed cert over
    path_cert = self._DATA_ROOT.joinpath("cert_not_ss.pem")
    path_key = self._DATA_ROOT.joinpath("key_not_ss.pem")

    shutil.copyfile(path_cert, p.ssl_cert_path)
    shutil.copyfile(path_key, p.ssl_key_path)

    enable_api_ui = False
    with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        s = server.Server(p, host, port, enable_api_ui)
    self.assertEqual("", fake_stderr.getvalue())
    self.assertEqual("", fake_stdout.getvalue())
    self.assertEqual(enable_api_ui, s._enable_api_ui)  # pylint: disable=protected-access

    s_server = s._server  # pylint: disable=protected-access
    connexion_app: connexion.FlaskApp = s_server.application
    self.assertEqual(enable_api_ui,
                     connexion_app.options.as_dict()["swagger_ui"])

  def test_run(self):
    path_db = self._TEST_ROOT.joinpath("portfolio.db")
    p = portfolio.Portfolio.create(path_db, None)

    path_cert = self._DATA_ROOT.joinpath("cert_ss.pem")
    path_key = self._DATA_ROOT.joinpath("key_ss.pem")

    shutil.copyfile(path_cert, p.ssl_cert_path)
    shutil.copyfile(path_key, p.ssl_key_path)

    host = "127.0.0.1"
    port = 8080
    url = f"https://localhost:{port}"
    enable_api_ui = True
    with mock.patch("sys.stderr", new=io.StringIO()) as _:
      s = server.Server(p, host, port, enable_api_ui)
    s_server = s._server  # pylint: disable=protected-access

    s_server.serve_forever = lambda *_: print("serve_forever")
    s_server.stop = lambda *_: print("stop")

    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      s.run()

    fake_stdout = fake_stdout.getvalue()
    target = (f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
              f"{Fore.CYAN}nummus API UI running on {url}/api/ui\n"
              "serve_forever\n"
              f"{Fore.YELLOW}nummus web shutdown at ")  # skip timestamp
    self.assertEqual(target, fake_stdout[:len(target)])

    enable_api_ui = False
    with mock.patch("sys.stderr", new=io.StringIO()) as _:
      s = server.Server(p, host, port, enable_api_ui)
    s_server = s._server  # pylint: disable=protected-access

    def raise_keyboard_interrupt():
      raise KeyboardInterrupt

    s_server.serve_forever = raise_keyboard_interrupt
    s_server.stop = lambda *_: print("stop")

    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      s.run()

    fake_stdout = fake_stdout.getvalue()
    target = (f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
              f"{Fore.YELLOW}Shutting down on interrupt\n"
              f"{Fore.YELLOW}nummus web shutdown at ")  # skip timestamp
    self.assertEqual(target, fake_stdout[:len(target)])

    # Artificially set started=True
    s_server._stop_event.clear()  # pylint: disable=protected-access
    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      s.run()

    fake_stdout = fake_stdout.getvalue()
    target = (f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
              f"{Fore.YELLOW}Shutting down on interrupt\n"
              "stop\n"
              f"{Fore.YELLOW}nummus web shutdown at ")  # skip timestamp
    self.assertEqual(target, fake_stdout[:len(target)])

  def test_generate_ssl_cert(self):
    path_cert = self._TEST_ROOT.joinpath("cert.pem")
    path_key = self._TEST_ROOT.joinpath("key.pem")

    server.Server.generate_ssl_cert(path_cert, path_key)

    self.assertTrue(path_cert.exists(), "SSL cert does not exist")
    self.assertTrue(path_key.exists(), "SSL key does not exist")
    self.assertEqual(path_cert.stat().st_mode & 0o777, 0o600)
    self.assertEqual(path_key.stat().st_mode & 0o777, 0o600)

    self.assertTrue(server.Server.is_ssl_cert_self_signed(path_cert),
                    "SSL cert is not self-signed")

  def test_is_ssl_cert_self_signed(self):
    path_cert = self._DATA_ROOT.joinpath("cert_ss.pem")
    self.assertTrue(server.Server.is_ssl_cert_self_signed(path_cert),
                    "SSL cert is not self-signed")

    path_cert = self._DATA_ROOT.joinpath("cert_not_ss.pem")
    self.assertFalse(server.Server.is_ssl_cert_self_signed(path_cert),
                     "SSL cert is self-signed")


class TestNummusJSONProvider(TestBase):
  """Test NummusJSONProvider class
  """

  def test_dumps(self):
    d = {"a": self.random_decimal(0, 1, precision=18)}

    target = f'{{"a": {d["a"]}}}'
    s = server.NummusJSONProvider.dumps(d)
    self.assertEqual(target, s)

  def test_loads(self):
    d = {"a": self.random_decimal(0, 1, precision=18)}
    s = server.NummusJSONProvider.dumps(d)
    d_loaded = server.NummusJSONProvider.loads(s)

    self.assertDictEqual(d, d_loaded)
