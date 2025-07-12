"""Web servers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import flask

from nummus.web.extension import FlaskExtension

if TYPE_CHECKING:
    from nummus.portfolio import Portfolio

ext = FlaskExtension()
portfolio: Portfolio


def create_app() -> flask.Flask:
    """Create flask app.

    Returns:
        NummusApp
    """
    path_root = Path(__file__).parent.parent.resolve()
    app = flask.Flask(
        __name__,
        static_folder=str(path_root / "static"),
        template_folder=str(path_root / "templates"),
    )
    ext.init_app(app)
    return app


def __getattr__(name: str) -> object:
    if name == "portfolio":
        return ext.portfolio
    msg = f"module {__name__} has no attribute {name}"
    raise AttributeError(msg)
