from __future__ import annotations

import datetime
import io
import os
from typing import NamedTuple
from unittest import mock

from nummus import portfolio
from nummus.web import server_base, server_production
from tests.base import TestBase


class LoggerConfig:
    loglevel: str

    def __getattribute__(self, name: str, /) -> object:
        try:
            return super().__getattribute__(name)
        except AttributeError:
            return None


class Request(NamedTuple):
    headers: list[tuple[str, str]]
    method: str
    uri: str


class Response(NamedTuple):
    response_length: int
    status_code: int


class TestServerProduction(TestBase):

    def test_init_properties(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        host = "127.0.0.1"
        port = 8080
        env = {"PROMETHEUS_MULTIPROC_DIR": str(self._TEST_ROOT)}
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch.dict(os.environ, env),
        ):
            s = server_production.Server(p, host, port)

        self.assertEqual(fake_stdout.getvalue(), "")

        app = s._app  # noqa: SLF001
        self.assertFalse(app.debug)


class TestLogger(TestBase):
    def test_access(self) -> None:
        cfg = LoggerConfig()
        cfg.loglevel = "info"
        h = server_production.GunicornLogger(cfg)

        original_format = server_base.NummusRequest.format
        try:
            logs: list[str] = []

            def info(msg: str) -> None:
                logs.append(msg)

            server_base.NummusRequest.format = lambda **kwargs: kwargs  # type: ignore[attr-defined]
            h.access_log.info = info  # type: ignore[attr-defined]

            logs.clear()
            req = Request([], "GET", "/")
            resp = Response(1000, 200)
            env = {"REMOTE_ADDR": "127.0.0.1"}
            req_time = datetime.timedelta(seconds=0.1)
            target = {
                "client_address": "127.0.0.1",
                "duration_s": 0.1,
                "method": "GET",
                "path": "/",
                "length_bytes": 1000,
                "status": 200,
            }
            h.access(resp, req, env, req_time)  # type: ignore[attr-defined]
            self.assertEqual(logs[0], target)

            logs.clear()
            req = Request([("X-REAL-IP", "192.168.1.2")], "GET", "/")
            resp = Response(1000, 200)
            env = {}
            req_time = datetime.timedelta(seconds=0.1)
            target = {
                "client_address": "192.168.1.2",
                "duration_s": 0.1,
                "method": "GET",
                "path": "/",
                "length_bytes": 1000,
                "status": 200,
            }
            h.access(resp, req, env, req_time)  # type: ignore[attr-defined]
            self.assertEqual(logs[0], target)

        finally:
            server_base.NummusRequest.format = original_format
