"""Web server for nummus
"""

import datetime
import pathlib

from colorama import Fore
import connexion
import gevent.pywsgi

from nummus import portfolio
from nummus.web import controller_html


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
    app = connexion.App(__name__, specification_dir=spec_dir, options=options)
    app.add_api("api.yaml",
                arguments={"title": "nummus API"},
                pythonic_params=True)
    app.add_url_rule("/", "", controller_html.get_home)

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