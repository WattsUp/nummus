import datetime
import io
import shutil
from decimal import Decimal
from unittest import mock

import flask
import time_machine
from colorama import Back, Fore

from nummus import __version__, portfolio, web
from tests.base import TestBase


class TestServer(TestBase):
    def test_init_properties(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        host = "127.0.0.1"
        port = 80
        debug = True

        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                s = web.Server(p, host, port, debug)
        fake_stderr = fake_stderr.getvalue()
        target = (
            f"{Fore.RED}No SSL certificate found at {p.ssl_cert_path}\n"
            f"{Fore.YELLOW}SSL certificate appears to be self-signed at "
            f"{p.ssl_cert_path}\n"
            "Replace with real certificate to disable this warning\n"
        )
        self.assertEqual(target, fake_stderr)
        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.MAGENTA}Running in debug mode\n"
            f"{Fore.MAGENTA}Generating self-signed certificate\n"
            "Please install certificate in web browser\n"
        )
        self.assertEqual(target, fake_stdout)

        self.assertEqual(p, s._portfolio)  # pylint: disable=protected-access

        s_server = s._server  # pylint: disable=protected-access
        flask_app = s._app  # pylint: disable=protected-access

        with flask_app.app_context():
            flask_p: portfolio.Portfolio = flask.current_app.portfolio
        self.assertEqual(p, flask_p)
        self.assertEqual(debug, flask_app.debug)

        self.assertEqual(host, s_server.server_host)
        self.assertEqual(port, s_server.server_port)

        # Copy not self-signed cert over
        path_cert = self._DATA_ROOT.joinpath("cert_not_ss.pem")
        path_key = self._DATA_ROOT.joinpath("key_not_ss.pem")

        shutil.copyfile(path_cert, p.ssl_cert_path)
        shutil.copyfile(path_key, p.ssl_key_path)

        debug = False
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                s = web.Server(p, host, port, debug)
        self.assertEqual("", fake_stderr.getvalue())
        self.assertEqual("", fake_stdout.getvalue())
        flask_app = s._app  # pylint: disable=protected-access
        self.assertEqual(debug, flask_app.debug)

    def test_run(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        path_cert = self._DATA_ROOT.joinpath("cert_ss.pem")
        path_key = self._DATA_ROOT.joinpath("key_ss.pem")

        shutil.copyfile(path_cert, p.ssl_cert_path)
        shutil.copyfile(path_key, p.ssl_key_path)

        host = "127.0.0.1"
        port = 8080
        url = f"https://localhost:{port}"
        debug = True
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                s = web.Server(p, host, port, debug)
        s_server = s._server  # pylint: disable=protected-access

        s_server.serve_forever = lambda *_: print("serve_forever")
        s_server.stop = lambda *_: print("stop")

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            s.run()

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
            "serve_forever\n"
            f"{Fore.YELLOW}nummus web shutdown at "
        )  # skip timestamp
        self.assertEqual(target, fake_stdout[: len(target)])

        debug = False
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                s = web.Server(p, host, port, debug)
        s_server = s._server  # pylint: disable=protected-access

        def raise_keyboard_interrupt() -> None:
            raise KeyboardInterrupt

        s_server.serve_forever = raise_keyboard_interrupt
        s_server.stop = lambda *_: print("stop")

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            s.run()

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
            f"{Fore.YELLOW}Shutting down on interrupt\n"
            f"{Fore.YELLOW}nummus web shutdown at "
        )  # skip timestamp
        self.assertEqual(target, fake_stdout[: len(target)])

        # Artificially set started=True
        s_server._stop_event.clear()  # pylint: disable=protected-access
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            s.run()

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)\n"
            f"{Fore.YELLOW}Shutting down on interrupt\n"
            "stop\n"
            f"{Fore.YELLOW}nummus web shutdown at "
        )  # skip timestamp
        self.assertEqual(target, fake_stdout[: len(target)])

    def test_generate_ssl_cert(self) -> None:
        path_cert = self._TEST_ROOT.joinpath("cert.pem")
        path_key = self._TEST_ROOT.joinpath("key.pem")

        web.Server.generate_ssl_cert(path_cert, path_key)

        self.assertTrue(path_cert.exists(), "SSL cert does not exist")
        self.assertTrue(path_key.exists(), "SSL key does not exist")
        self.assertEqual(path_cert.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path_key.stat().st_mode & 0o777, 0o600)

        self.assertTrue(
            web.Server.is_ssl_cert_self_signed(path_cert), "SSL cert is not self-signed"
        )

    def test_is_ssl_cert_self_signed(self) -> None:
        path_cert = self._DATA_ROOT.joinpath("cert_ss.pem")
        self.assertTrue(
            web.Server.is_ssl_cert_self_signed(path_cert), "SSL cert is not self-signed"
        )

        path_cert = self._DATA_ROOT.joinpath("cert_not_ss.pem")
        self.assertFalse(
            web.Server.is_ssl_cert_self_signed(path_cert), "SSL cert is self-signed"
        )

    def test_flask_context(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        path_cert = self._DATA_ROOT.joinpath("cert_ss.pem")
        path_key = self._DATA_ROOT.joinpath("key_ss.pem")

        shutil.copyfile(path_cert, p.ssl_cert_path)
        shutil.copyfile(path_key, p.ssl_key_path)

        host = "127.0.0.1"
        port = 8080
        debug = True
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                s = web.Server(p, host, port, debug)
        flask_app = s._app  # pylint: disable=protected-access

        with flask_app.app_context():
            target = __version__
            result = flask.render_template_string("{{ version }}")
            self.assertEqual(target, result)

    def test_jinja_filters(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        path_cert = self._DATA_ROOT.joinpath("cert_ss.pem")
        path_key = self._DATA_ROOT.joinpath("key_ss.pem")

        shutil.copyfile(path_cert, p.ssl_cert_path)
        shutil.copyfile(path_key, p.ssl_key_path)

        host = "127.0.0.1"
        port = 8080
        debug = True
        with mock.patch("sys.stderr", new=io.StringIO()) as _:
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                s = web.Server(p, host, port, debug)
        flask_app = s._app  # pylint: disable=protected-access

        with flask_app.app_context():
            context = {"number": Decimal("1000.100000")}
            target = "1000.100000"
            result = flask.render_template_string("{{ number }}", **context)
            self.assertEqual(target, result)

            target = "$1,000.10"
            result = flask.render_template_string("{{ number | money }}", **context)
            self.assertEqual(target, result)

            target = "1,000.10"
            result = flask.render_template_string("{{ number | comma }}", **context)
            self.assertEqual(target, result)

            context = {"duration": 14}
            target = "2 wks"
            result = flask.render_template_string("{{ duration | days }}", **context)
            self.assertEqual(target, result)


class TestHandler(TestBase):
    def test_format_request(self) -> None:
        h = web.Handler(None, None, None, "Not None")

        h.response_length = None
        utc_now = datetime.datetime.utcnow()
        with time_machine.travel(utc_now, tick=False):
            now = datetime.datetime.now().replace(microsecond=0)

        target = (
            f"[client address] [{now}] "
            "[delta t] [method] [endpoint] [HTTP ver] [len] [status]"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.response_length = 1000
        h.time_finish = 0.3
        h.time_start = 0.1
        h.client_address = ("127.0.0.1",)
        h.requestline = "GET / HTTP/1.1"
        h.code = 200
        target = (
            f"127.0.0.1 [{now}] {Fore.RED}0.200000s{Fore.RESET} "
            f"{Fore.CYAN}GET{Fore.RESET} "
            f"{Fore.GREEN}/{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.GREEN}200{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.time_finish = 0.2
        h.time_start = 0.1
        h.client_address = "127.0.0.1"
        h.requestline = "POST /static/dist/main.css HTTP/1.1"
        h.code = 300
        target = (
            f"127.0.0.1 [{now}] {Fore.YELLOW}0.100000s{Fore.RESET} "
            f"{Fore.GREEN}POST{Fore.RESET} "
            f"{Fore.MAGENTA}/static/dist/main.css{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.CYAN}300{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.time_finish = 0.15
        h.time_start = 0.1
        h.client_address = "127.0.0.1"
        h.requestline = "PUT /h/sidebar HTTP/1.1"
        h.code = 400
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            f"{Fore.YELLOW}PUT{Fore.RESET} "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.YELLOW}400{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.client_address = "127.0.0.1"
        h.requestline = "DELETE /h/sidebar HTTP/1.1"
        h.code = 500
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            f"{Fore.RED}DELETE{Fore.RESET} "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.RED}500{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.requestline = "OPTIONS /h/sidebar HTTP/1.1"
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            f"{Fore.BLUE}OPTIONS{Fore.RESET} "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.RED}500{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.requestline = "HEAD /h/sidebar HTTP/1.1"
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            f"{Fore.MAGENTA}HEAD{Fore.RESET} "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.RED}500{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.requestline = "PATCH /h/sidebar HTTP/1.1"
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            f"{Fore.BLACK}{Back.GREEN}PATCH{Fore.RESET}{Back.RESET} "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.RED}500{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.requestline = "TRACE /h/sidebar HTTP/1.1"
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            f"{Fore.BLACK}{Back.WHITE}TRACE{Fore.RESET}{Back.RESET} "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B "
            f"{Fore.RED}500{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)

        h.requestline = "GOT /h/sidebar HTTP/1.1"
        h.code = 600
        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.050000s{Fore.RESET} "
            "GOT "
            f"{Fore.CYAN}/h/sidebar{Fore.RESET} "
            "HTTP/1.1 1000B 600"
        )
        with time_machine.travel(utc_now, tick=False):
            result = h.format_request()
        self.assertEqual(target, result)


class TestTailwindCSSFilter(TestBase):
    def test_format_request(self) -> None:
        f = web.TailwindCSSFilter()

        out = io.StringIO()
        f.output(None, out)
        buf = out.getvalue()
        target = "/*! tailwindcss"
        self.assertEqual(target, buf[: len(target)])
