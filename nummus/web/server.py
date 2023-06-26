"""Web server for nummus
"""

import datetime
import pathlib

from colorama import Fore
import connexion
import gevent.pywsgi

from nummus import portfolio


class Server:
  """HTTP server that serves a nummus Portfolio
  """

  def __init__(self, p: portfolio.Portfolio) -> None:
    """Initialize Server

    Args:
      p: Portfolio to serve
    """
    self._portfolio = p
    self._server: gevent.pywsgi.WSGIServer = None

  def run(self, host: str = "127.0.0.1", port: int = 8080) -> None:
    """Start and run the server

    Args:
      host: Network address for server
      port Network port for server

    """
    spec_dir = pathlib.Path(__file__).parent.absolute().joinpath("spec")
    options = {"swagger_ui": True, "swagger_url": "/api/ui"}
    app = connexion.App(__name__, specification_dir=spec_dir, options=options)
    app.add_api("api.yaml",
                arguments={"title": "nummus API"},
                pythonic_params=True)

    self._server = gevent.pywsgi.WSGIServer((host, port), app)
    # TODO (WattsUp) Get https
    url = f"http://{self._server.server_host}:{self._server.server_port}"
    print(f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)")
    try:
      self._server.serve_forever()
    except KeyboardInterrupt:
      print(f"{Fore.YELLOW}Shutting down on interrupt")
      if self._server.started:
        self._server.stop()
    finally:
      now = datetime.datetime.utcnow().isoformat(timespec="seconds")
      print(f"{Fore.YELLOW}nummus web shutdown at {now}Z")
