"""Web server for nummus
"""

import datetime
import io
import pathlib
import sys
import typing as t
import warnings

from colorama import Fore, Back
import connexion
import flask
import flask_assets
import gevent.pywsgi
import pytailwindcss
from OpenSSL import crypto
import simplejson
import webassets.filter

from nummus import models, portfolio, version
from nummus import custom_types as t
from nummus.web import controller_html


class NummusWebHandler(gevent.pywsgi.WSGIHandler):
  """Custom WSGIHandler, mainly for request formatting
  """

  def format_request(self):
    """Format request as a single line

    Returns:
      [client address] [now] [delta t] [method] [endpoint] [HTTP ver] [len]
    """
    now = datetime.datetime.now().replace(microsecond=0)
    if self.response_length is None:
      length = "[len]"
    else:
      length = f"{self.response_length}B"

    if self.time_finish:
      delta = self.time_finish - self.time_start
      if delta > 0.15:
        delta = f"{Fore.RED}{delta:.6f}s{Fore.RESET}"
      elif delta > 0.075:
        delta = f"{Fore.YELLOW}{delta:.6f}s{Fore.RESET}"
      else:
        delta = f"{Fore.GREEN}{delta:.6f}s{Fore.RESET}"
    else:
      delta = "[delta t]"

    if self.client_address is None:
      client_address = "[client address]"
    elif isinstance(self.client_address, tuple):
      client_address = self.client_address[0]
    else:
      client_address = self.client_address

    if self.requestline is None:
      method = "[method]"
      endpoint = "[endpoint]"
      http_ver = "[HTTP ver]"
    else:
      method, endpoint, http_ver = self.requestline.split(" ")
      if method == "GET":
        method = f"{Fore.CYAN}{method}{Fore.RESET}"
      elif method == "POST":
        method = f"{Fore.GREEN}{method}{Fore.RESET}"
      elif method == "PUT":
        method = f"{Fore.YELLOW}{method}{Fore.RESET}"
      elif method == "DELETE":
        method = f"{Fore.RED}{method}{Fore.RESET}"
      elif method == "OPTIONS":
        method = f"{Fore.BLUE}{method}{Fore.RESET}"
      elif method == "HEAD":
        method = f"{Fore.MAGENTA}{method}{Fore.RESET}"
      elif method == "PATCH":
        method = f"{Fore.BLACK}{Back.GREEN}{method}{Fore.RESET}{Back.RESET}"
      elif method == "TRACE":
        method = f"{Fore.BLACK}{Back.WHITE}{method}{Fore.RESET}{Back.RESET}"

      if endpoint.startswith("/api/ui/"):
        endpoint = f"{Fore.CYAN}{endpoint}{Fore.RESET}"
      elif endpoint.startswith("/api/"):
        endpoint = f"{Fore.GREEN}{endpoint}{Fore.RESET}"
      elif endpoint.startswith("/static/"):
        endpoint = f"{Fore.MAGENTA}{endpoint}{Fore.RESET}"
      else:
        endpoint = f"{Fore.GREEN}{endpoint}{Fore.RESET}"

    return (f"{client_address} [{now}] {delta} "
            f"{method} {endpoint} {http_ver} {length}")


class TailwindCSSFilter(webassets.filter.Filter):
  """webassets Filter for running tailwindcss over
  """

  def output(
      self,
      _in: io.StringIO,  # pylint: disable=unused-argument,invalid-name
      out: io.StringIO,
      **_):
    """Run filter and generate output file

    Args:
      out: Output buffer
    """
    path_web = pathlib.Path(__file__).parent.resolve()
    path_config = path_web.joinpath("static", "tailwind.config.js")
    path_in = path_web.joinpath("static", "src", "main.css")

    args = ["-c", str(path_config), "-i", str(path_in), "--minify"]
    built_css = pytailwindcss.run(args, auto_install=True)
    out.write(built_css)


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

    # HTML pages routing
    app.add_url_rule("/", "", controller_html.get_home)
    app.add_url_rule("/index", "", controller_html.get_home)

    # Add Portfolio to context for controllers
    flask_app: flask.Flask = app.app
    with flask_app.app_context():
      flask.current_app.portfolio = p

    # Set JSON encoder
    # TODO (WattsUp) Fix deprecation warning once connexion updates
    with warnings.catch_warnings():
      warnings.simplefilter("ignore")
      flask_app.json = NummusJSONProvider(flask_app)

    # Enable debugger and reloader when enable_api_ui
    flask_app.debug = enable_api_ui

    # Inject common variables into templates
    flask_app.context_processor(lambda: {"version": version.__version__})

    # Setup environment and static file bundles
    env_assets = flask_assets.Environment(flask_app)

    bundle_css = flask_assets.Bundle("src/main.css",
                                     output="dist/main.css",
                                     filters=(TailwindCSSFilter,))
    env_assets.register("css", bundle_css)
    bundle_css.build()

    bundle_js = flask_assets.Bundle(
        "src/*.js",
        output="dist/main.js",
        filters=None if flask_app.debug else "jsmin")
    env_assets.register("js", bundle_js)
    bundle_js.build()

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
                                            keyfile=p.ssl_key_path,
                                            handler_class=NummusWebHandler)
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
