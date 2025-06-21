from __future__ import annotations

import io
import urllib.parse
import warnings
from unittest import mock

import flask

from nummus import encryption, portfolio, web
from tests.controllers.base import HTTP_CODE_REDIRECT, WebTestBase


class TestAuth(WebTestBase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not encryption.AVAILABLE:
            return
        cls._clean_test_root()

        # Create a portfolio for the test class
        # Need an encrypted portfolio
        cls._key = cls.random_string()
        path_db = cls._TEST_ROOT.joinpath("portfolio.db")
        cls._portfolio = portfolio.Portfolio.create(path_db, cls._key)

        with (
            mock.patch("sys.stderr", new=io.StringIO()) as _,
            mock.patch("sys.stdout", new=io.StringIO()) as _,
        ):
            # Ignore SSL warnings
            s = web.Server(cls._portfolio, "127.0.0.1", 8080, debug=False)
        cls._flask_app: flask.Flask = s._app  # noqa: SLF001
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            cls._client = cls._flask_app.test_client()

    def test_login(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")
        key = self._key

        # Not logged in should redirect any page to page_login
        endpoint = "accounts.page_all"
        with self._flask_app.app_context(), self._flask_app.test_request_context():
            url_next = flask.url_for(endpoint)
            url_dashboard = flask.url_for("dashboard.page")
            url_login = flask.url_for("auth.page_login")
            url_login_next = url_login + f"?next={urllib.parse.quote_plus(url_next)}"
        response, headers = self.web_get(endpoint, rc=HTTP_CODE_REDIRECT)
        self.assertIn(url_login_next, response)
        self.assertEqual(headers.get("Location"), url_login_next)

        # With HX-Request, return OK with HX-Redirect
        send_headers = {"HX-Request": "true"}
        response, headers = self.web_get(endpoint, headers=send_headers)
        self.assertEqual(response, "")
        self.assertEqual(headers.get("HX-Redirect"), url_login_next)

        # Static pages aren't protected
        self.web_get(
            ("static", {"filename": "img/favicon.ico"}),
            content_type="image/vnd.microsoft.icon",
        )

        # Login page isn't protected
        response, _ = self.web_get(("auth.page_login", {"next": url_next}))
        self.assertIn(f'value="{url_next}"', response)

        # Do login
        form = {}
        response, _ = self.web_post("auth.login", headers=send_headers, data=form)
        self.assertIn("Password must not be blank", response)

        # Wrong password
        form = {"password": self.random_string()}
        response, _ = self.web_post("auth.login", headers=send_headers, data=form)
        self.assertIn("Bad password", response)

        # Good password no next, goes to dashboard
        form = {"password": key}
        response, headers = self.web_post("auth.login", headers=send_headers, data=form)
        self.assertEqual("", response)
        self.assertEqual(headers.get("HX-Redirect"), url_dashboard)

        # Good password with next
        form = {"password": key, "next": url_next}
        response, headers = self.web_post("auth.login", headers=send_headers, data=form)
        self.assertEqual("", response)
        self.assertEqual(headers.get("HX-Redirect"), url_next)

        # Now can visit protected pages
        response, _ = self.web_get("dashboard.page")
        self.assertIn("Dashboard", response)

        # Login page while authenticated redirects to next
        response, headers = self.web_get(
            ("auth.page_login", {"next": url_next}),
            rc=HTTP_CODE_REDIRECT,
        )
        self.assertIn(url_next, response)
        self.assertEqual(headers.get("Location"), url_next)

        # No next goes to dashboard
        response, headers = self.web_get(
            "auth.page_login",
            rc=HTTP_CODE_REDIRECT,
        )
        self.assertIn(url_dashboard, response)
        self.assertEqual(headers.get("Location"), url_dashboard)

        # Logging out should redirect to login page
        response, headers = self.web_post(
            "auth.logout",
            headers=send_headers,
            data=form,
        )
        self.assertEqual("", response)
        self.assertEqual(headers.get("HX-Redirect"), url_login)

        # Can't visit protected pages anymore
        self.web_get("dashboard.page", rc=HTTP_CODE_REDIRECT)
