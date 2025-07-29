"""Gunicorn configuration."""  # noqa: INP001

from __future__ import annotations

import multiprocessing
from typing import TYPE_CHECKING

from prometheus_flask_exporter.multiprocess import GunicornPrometheusMetrics

if TYPE_CHECKING:
    import gunicorn.workers.base

workers = multiprocessing.cpu_count() * 2 + 1


def when_ready(_) -> None:
    """When gunicorn server is ready, start metrics server."""
    GunicornPrometheusMetrics.start_http_server_when_ready(8080)


def child_exit(_, worker: gunicorn.workers.base.Worker) -> None:
    """When gunicorn worker exits, kill metrics server."""
    GunicornPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)
