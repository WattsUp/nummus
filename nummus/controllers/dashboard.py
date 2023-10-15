"""Dashboard controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flask

from nummus.controllers import common

if TYPE_CHECKING:
    from nummus import custom_types as t


def page_home() -> str:
    """GET /.

    Returns:
        string HTML response
    """
    return flask.render_template("index.html", sidebar=common.ctx_sidebar())


ROUTES: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {
    "/": (page_home, ["GET"]),
    "/index": (page_home, ["GET"]),
}
