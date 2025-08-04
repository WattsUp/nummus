from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import flask
import pytest

from nummus import encryption
from nummus import exceptions as exc
from nummus import web
from nummus.models import Config, ConfigKey
from tests import conftest

if TYPE_CHECKING:
    from pathlib import Path

    from nummus.portfolio import Portfolio


def test_create_app(empty_portfolio: Portfolio, flask_app: flask.Flask) -> None:
    with empty_portfolio.begin_session() as s:
        secret_key = (
            s.query(Config.value).where(Config.key == ConfigKey.SECRET_KEY).one()[0]
        )
    assert flask_app.secret_key == secret_key
    assert len(flask_app.before_request_funcs[None]) == 1

    assert web.portfolio.path == empty_portfolio.path


def test_no_secret_key(
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio: Portfolio,
) -> None:
    monkeypatch.setenv("NUMMUS_PORTFOLIO", str(empty_portfolio.path))
    with empty_portfolio.begin_session() as s:
        s.query(Config).where(Config.key == ConfigKey.SECRET_KEY).delete()

    with pytest.raises(exc.ProtectedObjectNotFoundError):
        web.create_app()


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_create_app_encrypted(
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> None:
    p, key = empty_portfolio_encrypted
    monkeypatch.setenv("NUMMUS_PORTFOLIO", str(p.path))
    monkeypatch.setenv("NUMMUS_KEY", key)

    app = web.create_app()
    assert len(app.before_request_funcs[None]) == 2


@pytest.mark.skipif(not encryption.AVAILABLE, reason="No encryption available")
@pytest.mark.encryption
def test_create_app_encrypted_key_file(
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
    tmp_path: Path,
) -> None:
    p, key = empty_portfolio_encrypted
    path_key = tmp_path / "key"
    with path_key.open("w", encoding="utf-8") as file:
        file.write(key)
    monkeypatch.setenv("NUMMUS_PORTFOLIO", str(p.path))
    monkeypatch.setenv("NUMMUS_KEY_PATH", str(path_key))

    app = web.create_app()
    assert len(app.before_request_funcs[None]) == 2


def test_getattr() -> None:
    with pytest.raises(AttributeError):
        _ = web.fake


@pytest.mark.parametrize(
    ("kwargs", "target"),
    [
        ({}, ""),
        ({"boolean": True}, "?boolean="),
        ({"boolean": False}, ""),
        ({"uri": None}, ""),
        ({"string": "abc"}, "?string=abc"),
        ({"string": ""}, ""),
        ({"integer": 0}, "?integer=0"),
        ({"integer": 1}, "?integer=1"),
    ],
    ids=conftest.id_func,
)
def test_url_for(
    flask_app: flask.Flask,
    kwargs: dict[str, object],
    target: str,
) -> None:
    with flask_app.test_request_context():
        result = flask_app.url_for(
            "static",
            filename="main.css",
            _anchor=None,
            _method=None,
            _scheme=None,
            _external=False,
            **kwargs,
        )
        assert result == "/static/main.css" + target


def test_flask_context(flask_app: flask.Flask) -> None:
    with flask_app.app_context():
        assert flask.render_template_string("{{ url_args }}") == "{}"


@pytest.mark.parametrize(
    ("value", "filt", "target"),
    [
        (Decimal("1000.100000"), "money", "$1,000.10"),
        (Decimal("-1000.100000"), "money", "-$1,000.10"),
        (Decimal("1000.100000"), "money0", "$1,000"),
        (Decimal("1000.100000"), "money6", "$1,000.100000"),
        (Decimal("1000.100000"), "comma", "1,000.10"),
        (Decimal("1000.100000"), "qty", "1,000.100000"),
        (Decimal("1000.100000"), "input_value", "1000.1"),
        (Decimal("1000.000000"), "input_value", "1000"),
        (Decimal(), "input_value", ""),
        (Decimal(1), "pnl_color", "text-primary"),
        (Decimal(), "pnl_color", ""),
        (Decimal(-1), "pnl_color", "text-error"),
        (Decimal(1), "pnl_arrow", "arrow_upward"),
        (Decimal(), "pnl_arrow", ""),
        (Decimal(-1), "pnl_arrow", "arrow_downward"),
        (14, "days", "2 weeks"),
        (14, "days_abv", "2 wks"),
        (Decimal("0.1234"), "percent", "12.34%"),
    ],
    ids=conftest.id_func,
)
def test_jinja_filters(
    flask_app: flask.Flask,
    value: object,
    filt: str,
    target: str,
) -> None:
    with flask_app.test_request_context():
        result = flask.render_template_string(
            f"{{{{ value | {filt} }}}}",
            value=value,
        )
        assert result == target
