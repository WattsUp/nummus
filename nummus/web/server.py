"""Web server for nummus
"""

import datetime
import pathlib
import sys
import warnings

from colorama import Fore
import connexion
import flask
import gevent.pywsgi
from OpenSSL import crypto
import simplejson

from nummus import models, portfolio
from nummus import custom_types as t
from nummus.web import controller_html


class NummusJSONProvider(flask.json.provider.JSONProvider):
  """Custom JSON Provider for nummus models

  Loads and dumps real numbers as Decimals
  """

  @classmethod
  def loads(cls, s: str, **kwargs: t.DictAny) -> t.Any:
    """Deserialize data as JSON

    Args:
      s: Text to deserialize

    Returns:
      Deserialized object
    """
    return simplejson.loads(s, **kwargs, use_decimal=True)

  @classmethod
  def dumps(cls, obj: t.Any, **kwargs: t.DictAny) -> str:
    """Serialize data as JSON

    Args:
      obj: The data to serialize

    Returns:
      Serialized object as a string
    """
    return simplejson.dumps(obj,
                            **kwargs,
                            use_decimal=True,
                            cls=models.NummusJSONEncoder)


class Server:
  """HTTP server that serves a nummus Portfolio
  """

  def __init__(self, p: portfolio.Portfolio, host: str, port: int,
               enable_api_ui: bool) -> None:
    """Initialize Server

    Args:
      p: Portfolio to serve
      host: IP to bind to
      port: Network port to bind to
      enable_api_ui: True will enable Swagger UI for the API
    """
    self._portfolio = p

    spec_dir = pathlib.Path(__file__).parent.absolute().joinpath("spec")
    options = {"swagger_ui": enable_api_ui}
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      app = connexion.App(__name__, specification_dir=spec_dir, options=options)
      app.add_api("api.yaml",
                  arguments={"title": "nummus API"},
                  pythonic_params=True,
                  strict_validation=True)
    app.add_url_rule("/", "", controller_html.get_home)

    # Add Portfolio to context for controllers
    flask_app: flask.Flask = app.app
    with flask_app.app_context():
      flask.current_app.portfolio = p

    # Set JSON encoder
    # TODO (WattsUp) Fix deprecation warning once connexion updates
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      flask_app.json = NummusJSONProvider(flask_app)

    if not p.ssl_cert_path.exists():
      print(f"{Fore.RED}No SSL certificate found at {p.ssl_cert_path}",
            file=sys.stderr)
      print(f"{Fore.MAGENTA}Generating self-signed certificate")
      self.generate_ssl_cert(p.ssl_cert_path, p.ssl_key_path)
      print("Please install certificate in web browser")

    # Check for self-signed SSL cert
    if self.is_ssl_cert_self_signed(p.ssl_cert_path):
      buf = (f"{Fore.YELLOW}SSL certificate appears to be self-signed at "
             f"{p.ssl_cert_path}\n"
             "Replace with real certificate to disable this warning")
      print(buf, file=sys.stderr)

    self._server = gevent.pywsgi.WSGIServer((host, port),
                                            app,
                                            certfile=p.ssl_cert_path,
                                            keyfile=p.ssl_key_path)
    self._enable_api_ui = enable_api_ui

  def run(self) -> None:
    """Start and run the server
    """
    url = f"https://localhost:{self._server.server_port}"
    print(f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)")
    if self._enable_api_ui:
      print(f"{Fore.CYAN}nummus API UI running on {url}/api/ui")
    try:
      self._server.serve_forever()
    except KeyboardInterrupt:
      print(f"{Fore.YELLOW}Shutting down on interrupt")
      if self._server.started:
        self._server.stop()
    finally:
      now = datetime.datetime.utcnow().isoformat(timespec="seconds")
      print(f"{Fore.YELLOW}nummus web shutdown at {now}Z")

  @staticmethod
  def generate_ssl_cert(path_cert: pathlib.Path,
                        path_key: pathlib.Path) -> None:
    """Generate a self-signed SSL certificate

    Args:
      path_cert: Path to SSL certificate
      path_key: Path to SSL certificate signing key
    """
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 4096)

    cert = crypto.X509()
    cert.set_version(2)  # Version x509v3 for SAN
    cert.get_subject().CN = "localhost"
    san_list = ["DNS:localhost"]
    cert.add_extensions([
        crypto.X509Extension(b"subjectAltName", False,
                             ", ".join(san_list).encode())
    ])
    cert.set_serial_number(0)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)  # 10 yrs in seconds
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, "sha512")

    with open(path_cert, "wb") as file:
      file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    with open(path_key, "wb") as file:
      file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

    path_cert.chmod(0o600)
    path_key.chmod(0o600)

  @staticmethod
  def is_ssl_cert_self_signed(path_cert: pathlib.Path) -> bool:
    """Check if SSL certificate is self-signed

    Args:
      path_cert: Path to SSL certificate

    Returns:
      True if CN=localhost, False otherwise
    """
    with open(path_cert, "rb") as file:
      buf = file.read()
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, buf)
    return cert.get_subject().CN == "localhost"
