from __future__ import annotations

import datetime
from decimal import Decimal

import flask
import time_machine
from colorama import Fore

from nummus import __version__, encryption, portfolio
from nummus.models import Config, ConfigKey
from nummus.web import server_base
from tests.base import TestBase


class TestServerBase(TestBase):

    def test_create_app(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        debug = True
        app = server_base.create_flask_app(p, debug=debug)

        with app.app_context():
            flask_p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]
        self.assertEqual(flask_p, p)
        self.assertEqual(app.debug, debug)

        self.assertEqual(app.request_class, server_base.NummusRequest)

        with p.begin_session() as s:
            secret_key = (
                s.query(Config.value).where(Config.key == ConfigKey.SECRET_KEY).scalar()
            )
        self.assertEqual(app.secret_key, secret_key)
        self.assertEqual(len(app.before_request_funcs[None]), 1)

        if not encryption.AVAILABLE:
            return
        path_db.unlink()
        p = portfolio.Portfolio.create(path_db, self.random_string())
        app = server_base.create_flask_app(p, debug=debug)
        # encrypted gets login required
        self.assertEqual(len(app.before_request_funcs[None]), 2)

    def test_flask_context(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        app = server_base.create_flask_app(p, debug=True)

        with app.app_context():
            target = __version__
            result = flask.render_template_string("{{ version }}")
            self.assertEqual(result, target)

    def test_jinja_filters(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        p = portfolio.Portfolio.create(path_db, None)

        app = server_base.create_flask_app(p, debug=True)

        with app.app_context():
            context = {"number": Decimal("1000.100000")}
            target = "1000.100000"
            result = flask.render_template_string("{{ number }}", **context)
            self.assertEqual(result, target)

            target = "$1,000.10"
            result = flask.render_template_string("{{ number | money }}", **context)
            self.assertEqual(result, target)

            target = "$1,000"
            result = flask.render_template_string("{{ number | money0 }}", **context)
            self.assertEqual(result, target)

            target = "$1,000.100000"
            result = flask.render_template_string("{{ number | money6 }}", **context)
            self.assertEqual(result, target)

            target = "1,000.10"
            result = flask.render_template_string("{{ number | comma }}", **context)
            self.assertEqual(result, target)

            target = "1,000.100000"
            result = flask.render_template_string("{{ number | qty }}", **context)
            self.assertEqual(result, target)

            target = "text-primary"
            result = flask.render_template_string("{{ number | pnl_color }}", **context)
            self.assertEqual(result, target)

            target = "arrow_upward"
            result = flask.render_template_string("{{ number | pnl_arrow }}", **context)
            self.assertEqual(result, target)

            target = "1000.1"
            result = flask.render_template_string(
                "{{ number | input_value }}",
                **context,
            )
            self.assertEqual(result, target)

            context = {"number": Decimal("-0.12345")}
            target = "text-error"
            result = flask.render_template_string("{{ number | pnl_color }}", **context)
            self.assertEqual(result, target)

            target = "arrow_downward"
            result = flask.render_template_string("{{ number | pnl_arrow }}", **context)
            self.assertEqual(result, target)

            context = {"number": Decimal(0)}
            target = ""
            result = flask.render_template_string("{{ number | pnl_color }}", **context)
            self.assertEqual(result, target)

            target = ""
            result = flask.render_template_string("{{ number | pnl_arrow }}", **context)
            self.assertEqual(result, target)

            target = ""
            result = flask.render_template_string(
                "{{ number | input_value }}",
                **context,
            )
            self.assertEqual(result, target)

            context = {"number": Decimal("1000.0000")}
            target = "1000"
            result = flask.render_template_string(
                "{{ number | input_value }}",
                **context,
            )
            self.assertEqual(result, target)

            context = {"duration": 14}
            target = "2 weeks"
            result = flask.render_template_string("{{ duration | days }}", **context)
            self.assertEqual(result, target)

            context = {"duration": 14}
            target = "2 wks"
            result = flask.render_template_string(
                "{{ duration | days_abv }}",
                **context,
            )
            self.assertEqual(result, target)

            context = {"number": Decimal("0.123456")}
            target = "12.35%"
            result = flask.render_template_string("{{ number | percent }}", **context)
            self.assertEqual(result, target)


class TestNummusApp(TestBase):
    def test_url_for(self) -> None:
        flask_app = server_base.NummusApp(__file__)

        with flask_app.app_context(), flask_app.test_request_context():
            result = flask_app.url_for("static", filename="main.css")
            target = "/static/main.css"
            self.assertEqual(result, target)

            result = flask_app.url_for("static", filename="main.css", boolean=True)
            target = "/static/main.css?boolean="
            self.assertEqual(result, target)

            result = flask_app.url_for("static", filename="main.css", boolean=False)
            target = "/static/main.css"
            self.assertEqual(result, target)

            result = flask_app.url_for("static", filename="main.css", uri=None)
            target = "/static/main.css"
            self.assertEqual(result, target)

            result = flask_app.url_for("static", filename="main.css", string="abc")
            target = "/static/main.css?string=abc"
            self.assertEqual(result, target)

            result = flask_app.url_for("static", filename="main.css", string="")
            target = "/static/main.css"
            self.assertEqual(result, target)

            result = flask_app.url_for("static", filename="main.css", integer=0)
            target = "/static/main.css?integer=0"
            self.assertEqual(result, target)


class TestNummusRequest(TestBase):
    def test_format(self) -> None:
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        with time_machine.travel(utc_now, tick=False):
            now = datetime.datetime.now().astimezone().replace(microsecond=0)

        target = (
            f"127.0.0.1 [{now}] {Fore.RED}0.200s{Fore.RESET} "
            f"{Fore.CYAN}GET{Fore.RESET} "
            f"{Fore.GREEN}/{Fore.RESET} "
            f"{Fore.GREEN}1000B{Fore.RESET} "
            f"{Fore.GREEN}200{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = server_base.NummusRequest.format(
                client_address="127.0.0.1",
                duration_s=0.2,
                method="GET",
                path="/",
                length_bytes=1000,
                status=200,
            )
        self.assertEqual(result, target)

        target = (
            f"127.0.0.1 [{now}] {Fore.YELLOW}0.100s{Fore.RESET} "
            f"{Fore.GREEN}POST{Fore.RESET} "
            f"{Fore.MAGENTA}/static/dist/main.css{Fore.RESET} "
            f"{Fore.YELLOW}500001B{Fore.RESET} "
            f"{Fore.CYAN}300{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = server_base.NummusRequest.format(
                client_address="127.0.0.1",
                duration_s=0.1,
                method="POST",
                path="/static/dist/main.css",
                length_bytes=500001,
                status=300,
            )
        self.assertEqual(result, target)

        target = (
            f"127.0.0.1 [{now}] {Fore.GREEN}0.010s{Fore.RESET} "
            f"{Fore.YELLOW}PUT{Fore.RESET} "
            "unknown "
            f"{Fore.RED}1000001B{Fore.RESET} "
            f"{Fore.YELLOW}400{Fore.RESET}"
        )
        with time_machine.travel(utc_now, tick=False):
            result = server_base.NummusRequest.format(
                client_address="127.0.0.1",
                duration_s=0.01,
                method="PUT",
                path="unknown",
                length_bytes=1000001,
                status=400,
            )
        self.assertEqual(result, target)
