from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

import flask
import pytest

from nummus.controllers.base import HTTP_CODE_OK, HTTP_CODE_REDIRECT
from nummus.models import Config, ConfigKey

if TYPE_CHECKING:
    import werkzeug.datastructures

    from nummus.portfolio import Portfolio


ResultType = dict[str, object] | str | bytes
Tree = dict[str, "TreeNode"]
TreeNode = Tree | tuple[str, Tree, int] | object
Queries = dict[str, str] | dict[str, str | bool | list[str | bool]]


class HTMLValidator:

    @classmethod
    def __call__(cls, s: str) -> bool:
        tags: list[tuple[str, int, int]] = [
            (m.group(1), m.start(0), m.end(0))
            for m in re.finditer(r"<(/?\w+)(?:[^<>]+)?>", s)
        ]

        tree: Tree = {"__parent__": (None, None, None)}
        current_node = tree
        for tag, i_start, i_end in tags:
            assert isinstance(current_node, dict)
            if tag[0] == "/":
                # Close tag
                item = current_node.pop("__parent__")
                assert isinstance(item, tuple)
                current_tag, parent, open_i_end = item
                current_node = parent
                assert current_tag == tag[1:]

                inner_html = s[open_i_end:i_start]
                if current_tag in {"h1", "h2", "h3", "h4"} and inner_html != "nummus":
                    # Headers should use capital case
                    # strip any inner element
                    inner_html = inner_html.replace(".", "")
                    words = inner_html.split(" ")
                    target = " ".join(
                        (
                            w
                            if w.upper() == w
                            else (w.capitalize() if i == 0 else w.lower())
                        )
                        for i, w in enumerate(words)
                    )
                    assert inner_html == target
            elif tag in {"link", "meta", "path", "input", "hr", "rect"}:
                # Tags without close tags
                current_node[tag] = {}
            else:
                current_node[tag] = {"__parent__": (tag, current_node, i_end)}
                current_node = current_node[tag]

        # Got back up to the root element
        assert isinstance(current_node, dict)
        item = current_node.pop("__parent__")
        assert isinstance(item, tuple)
        tag, parent, _ = item
        assert tag in {None, "html"}  # <html> might not be closed
        if parent is not None:
            parent: dict[str, object]
            assert parent.keys() == {"__parent__", "html"}

        # Find all DOM ids and validate no duplicates
        ids: list[str] = re.findall(r'id="([^"]+)"', s)
        id_counts: dict[str, int] = defaultdict(int)
        for e_id in ids:
            id_counts[e_id] += 1
        duplicates = {e_id for e_id, count in id_counts.items() if count != 1}
        assert not duplicates
        return True


@pytest.fixture(scope="session")
def valid_html() -> HTMLValidator:
    """Returns a HTMLValidator.

    Returns:
        HTMLValidator
    """
    return HTMLValidator()


class WebClient:

    def __init__(self, app: flask.Flask, valid_html: HTMLValidator) -> None:
        self._flask_app = app
        self._client = self._flask_app.test_client()
        self.valid_html = valid_html

        self.raw_open = self._client.open

    def url_for(self, endpoint: str, **url_args: object) -> str:
        with self._flask_app.app_context(), self._flask_app.test_request_context():
            return flask.url_for(
                endpoint,
                _anchor=None,
                _method=None,
                _scheme=None,
                _external=False,
                **url_args,
            )

    def open_(
        self,
        method: str,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """Run a test HTTP request.

        Args:
            method: HTTP method to use
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        if isinstance(endpoint, str):
            url_args = {}
        else:
            endpoint, url_args = endpoint
        url = self.url_for(endpoint, **url_args)

        kwargs["method"] = method
        kwargs["headers"] = kwargs.get("headers", {"HX-Request": "true"})
        response: werkzeug.test.TestResponse | None = None
        try:
            response = self._client.open(
                url,
                buffered=False,
                follow_redirects=False,
                **kwargs,
            )
            assert response.status_code == rc
            assert response.content_type == content_type

            if content_type == "text/html; charset=utf-8":
                html = response.text
                # Remove whitespace
                html = "".join(html.split("\n"))
                html = re.sub(r" +", " ", html)
                html = re.sub(r" ?> ?", ">", html)
                html = re.sub(r" ?< ?", "<", html)
                if response.status_code != HTTP_CODE_REDIRECT:
                    # werkzeug redirect doesn't have close tags
                    assert self.valid_html(html)
                return html, response.headers
            return response.data, response.headers
        finally:
            if response is not None:
                response.close()

    def GET(  # noqa: N802
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """GET an HTTP response.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.open_("GET", endpoint, rc=rc, content_type=content_type, **kwargs)

    def PUT(  # noqa: N802
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """PUT an HTTP response.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.open_("PUT", endpoint, rc=rc, content_type=content_type, **kwargs)

    def POST(  # noqa: N802
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """POST an HTTP response.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.open_("POST", endpoint, rc=rc, content_type=content_type, **kwargs)

    def DELETE(  # noqa: N802
        self,
        endpoint: str | tuple[str, Queries],
        *,
        rc: int = HTTP_CODE_OK,
        content_type: str = "text/html; charset=utf-8",
        **kwargs: object,
    ) -> tuple[str, werkzeug.datastructures.Headers]:
        """DELETE an HTTP response.

        Args:
            endpoint: Route endpoint to test or (endpoint, url_for kwargs)
            rc: Expected HTTP return code
            content_type: Content type to check for
            kwargs: Passed to client.get

        Returns:
            (response.text, headers)
        """
        return self.open_(
            "DELETE",
            endpoint,
            rc=rc,
            content_type=content_type,
            **kwargs,
        )


@pytest.fixture
def web_client(flask_app: flask.Flask, valid_html: HTMLValidator) -> WebClient:
    """Returns a WebClient.

    Returns:
        WebClient
    """
    return WebClient(flask_app, valid_html)


class WebClientEncrypted(WebClient):

    def __init__(
        self,
        app: flask.Flask,
        valid_html: HTMLValidator,
        portfolio: Portfolio,
    ) -> None:
        super().__init__(app, valid_html)

        with portfolio.begin_session() as s:
            key_encoded = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).one()[0]
            )

        self._web_key = portfolio.decrypt(key_encoded)

    def login(self) -> None:
        """Login user."""
        self.POST("auth.login", data={"password": self._web_key})


@pytest.fixture
def web_client_encrypted(
    flask_app_encrypted: flask.Flask,
    valid_html: HTMLValidator,
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> WebClientEncrypted:
    """Returns a WebClient.

    Returns:
        WebClient
    """
    p, _ = empty_portfolio_encrypted
    return WebClientEncrypted(flask_app_encrypted, valid_html, p)
