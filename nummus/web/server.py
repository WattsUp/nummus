"""Web server for nummus
"""

import typing as t

import datetime
import pathlib
import warnings

from colorama import Fore
import connexion
import flask
import gevent.pywsgi
import simplejson

from nummus import models, portfolio
from nummus.web import controller_html


class NummusJSONProvider(flask.json.provider.JSONProvider):
  """Custom JSON Provider for nummus models

  Loads and dumps real numbers as Decimals
  """

  @classmethod
  def loads(cls, s: str, **kwargs: t.Dict[str, object]) -> t.Dict[str, object]:
    return simplejson.loads(s, **kwargs, use_decimal=True)

  @classmethod
  def dumps(cls, obj: object, **kwargs: t.Dict[str, object]) -> str:
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

    self._server = gevent.pywsgi.WSGIServer((host, port), app)
    self._enable_api_ui = enable_api_ui

  def run(self) -> None:
    """Start and run the server
    """
    # TODO (WattsUp) Get https
    url = f"http://{self._server.server_host}:{self._server.server_port}"
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
