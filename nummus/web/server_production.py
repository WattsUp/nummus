"""Production web server for nummus."""

from __future__ import annotations

import multiprocessing
import traceback
from typing import TYPE_CHECKING

import gunicorn.app.base
import gunicorn.glogging
import gunicorn.http.message
import gunicorn.http.wsgi
import gunicorn.workers.base
from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics
from typing_extensions import override

from nummus.web import server_base

if TYPE_CHECKING:
    import datetime

    from _typeshed.wsgi import WSGIApplication

    from nummus import portfolio


class GunicornLogger(gunicorn.glogging.Logger):
    """Logger class for gunicorn."""

    @override
    def access(
        self,
        resp: gunicorn.http.wsgi.Response,
        req: gunicorn.http.message.Request,
        environ: dict[str, object],
        request_time: datetime.timedelta,
    ) -> None:
        headers = req.headers

        try:
            client_address = next(v for k, v in headers if k == "X-REAL-IP")
        except StopIteration:
            client_address = str(environ.get("REMOTE_ADDR", "[client address]"))

        msg = server_base.NummusRequest.format(
            client_address=client_address,
            duration_s=request_time.total_seconds(),
            method=req.method or "[method]",
            path=req.uri or "[path]",
            length_bytes=resp.response_length or 0,
            status=resp.status_code or 0,
        )
        try:
            self.access_log.info(msg)
        except Exception:  # noqa: BLE001 # pragma: no cover
            self.error(traceback.format_exc())


class Server(gunicorn.app.base.BaseApplication):
    """HTTP server that serves nummus for production."""

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
        self._app = server_base.create_flask_app(p, debug=False)
        self._access_log = p.path.with_suffix(".access.log")
        self._host = host
        self._port = port
        super().__init__()

    @override
    def load_config(self) -> None:
        config = {
            "bind": f"{self._host}:{self._port}",
            "workers": multiprocessing.cpu_count() * 2 + 1,
            "accesslog": str(self._access_log),
            "logger_class": GunicornLogger,
            "when_ready": self.when_ready,
            "child_exit": self.child_exit,
        }
        if self.cfg is None:  # pragma: no cover
            msg = "cfg is None"
            raise TypeError(msg)
        for k, v in config.items():
            self.cfg.set(k, v)

    @override
    def load(self) -> WSGIApplication:  # pragma: no cover
        return self._app

    def when_ready(self, _) -> None:  # pragma: no cover
        """When server is ready, start GunicornPrometheusMetrics."""
        GunicornPrometheusMetrics.start_http_server_when_ready(
            port=self._port + 1,
            host=self._host,
        )

    @classmethod
    def child_exit(
        cls,
        _,
        worker: gunicorn.workers.base.Worker,
    ) -> None:  # pragma: no cover
        """When server is ready, start GunicornPrometheusMetrics."""
        GunicornPrometheusMetrics.mark_process_dead_on_child_exit(
            worker.pid,
        )
