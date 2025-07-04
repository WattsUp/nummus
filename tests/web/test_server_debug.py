from __future__ import annotations

import io
from unittest import mock

from nummus import portfolio
from nummus.web import server_base, server_debug
from tests.base import TestBase


class TestServerDebug(TestBase):

    def test_init_properties(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        host = "127.0.0.1"
        port = 8080
        s = server_debug.Server(p, host, port)
        app = s._app  # noqa: SLF001
        self.assertTrue(app.debug)

    def test_run(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        host = "127.0.0.1"
        port = 8080
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            s = server_debug.Server(p, host, port)
        s_server = s._server  # noqa: SLF001

        s_server.serve_forever = lambda *_: print("serve_forever")  # type: ignore[attr-defined] # noqa: T201
        s_server.stop = lambda **_: print("stop")  # type: ignore[attr-defined] # noqa: T201

        with (mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,):
            s.run()
        target = "serve_forever\n"
        self.assertEqual(fake_stdout.getvalue(), target)

        def raise_keyboard_interrupt() -> None:
            raise KeyboardInterrupt

        s_server.serve_forever = raise_keyboard_interrupt  # type: ignore[attr-defined]
        s_server.stop = lambda **_: print("stop")  # type: ignore[attr-defined] # noqa: T201

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            s.run()

        self.assertEqual(fake_stdout.getvalue(), "")

        # Artificially set started=True
        s_server._stop_event.clear()  # noqa: SLF001 # type: ignore[attr-defined]
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            s.run()

        fake_stdout = fake_stdout.getvalue()
        target = "stop\n"
        self.assertEqual(fake_stdout, target)


class TestHandler(TestBase):
    def test_format_request(self) -> None:
        h = server_debug.Handler(None, None, None, rfile="")  # type: ignore[attr-defined]

        original_format = server_base.NummusRequest.format
        try:
            server_base.NummusRequest.format = lambda **kwargs: kwargs  # type: ignore[attr-defined]

            target = {
                "client_address": "[client address]",
                "duration_s": -1,
                "method": "[method]",
                "path": "[path]",
                "length_bytes": 0,
                "status": 0,
            }
            result = h.format_request()
            self.assertEqual(result, target)

            h.response_length = 1000
            h.time_finish = 0.3
            h.time_start = 0.1
            h.client_address = ("127.0.0.1",)  # type: ignore[attr-defined]
            h.requestline = "GET / HTTP/1.1"
            h.code = 200
            target = {
                "client_address": "127.0.0.1",
                "duration_s": 0.3 - 0.1,  # floating point, grr
                "method": "GET",
                "path": "/",
                "length_bytes": 1000,
                "status": 200,
            }
            result = h.format_request()
            self.assertEqual(result, target)

            h.headers["X-Real-IP"] = "192.168.1.2"
            target = {
                "client_address": "192.168.1.2",
                "duration_s": 0.3 - 0.1,  # floating point, grr
                "method": "GET",
                "path": "/",
                "length_bytes": 1000,
                "status": 200,
            }
            result = h.format_request()
            self.assertEqual(result, target)
        finally:
            server_base.NummusRequest.format = original_format
