"""Debug web server for nummus."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gevent.pool
import gevent.pywsgi

from nummus.web import server_base

if TYPE_CHECKING:
    from nummus import portfolio


class Handler(gevent.pywsgi.WSGIHandler):
    """Custom WSGIHandler, mainly for request formatting."""

    def format_request(self) -> str:
        """Format request as a single line."""
        if "X-Real-IP" in self.headers:
            client_address = self.headers["X-Real-IP"]
        elif isinstance(self.client_address, tuple):
            client_address = self.client_address[0]
        else:
            client_address = self.client_address or "[client address]"

        if self.requestline is None:
            method = "[method]"
            path = "[path]"
        else:
            try:
                method, path, _ = self.requestline.split(" ")
            except ValueError:  # pragma: no cover
                # This usually comes during IS penetration testing
                method = f"{self.requestline.encode()}?"
                path = ""

        return server_base.NummusRequest.format(
            client_address=client_address,
            duration_s=(self.time_finish - self.time_start) if self.time_finish else -1,
            method=method,
            path=path,
            length_bytes=getattr(self, "response_length", 0),
            status=self.code or 0,
        )


class Server:
    """HTTP server that serves nummus for debugging."""

    def __init__(
        self,
        p: portfolio.Portfolio,
        host: str,
        port: int,
    ) -> None:
        """Initialize Server.

        Args:
            p: Portfolio to serve
            host: IP to bind to
            port: Network port to bind to
        """
        self._app = server_base.create_flask_app(p, debug=True)

        self._pool = gevent.pool.Pool(1000)

        self._server = gevent.pywsgi.WSGIServer(
            (host, port),
            self._app,
            handler_class=Handler,
            spawn=self._pool,
        )

    def run(self) -> None:
        """Start and run the server."""
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            if self._server.started:
                self._server.stop(timeout=1)
        finally:
            self._server.close()
