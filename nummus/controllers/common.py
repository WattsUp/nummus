"""Common component controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import auth, base

if TYPE_CHECKING:
    import flask


def page_dashboard() -> flask.Response:
    """GET /.

    Returns:
        string HTML response
    """
    return base.page("page.jinja", title="Dashboard | nummus")


@auth.login_exempt
def page_status() -> str:
    """GET /status.

    Returns:
        string HTML response
    """
    return "ok"


def page_style_test() -> flask.Response:
    """GET /style-test.

    Returns:
        string HTML response
    """
    return base.page(
        "shared/style-test.jinja",
        "Style Test",
    )


ROUTES: base.Routes = {
    "/": (page_dashboard, ["GET"]),
    "/index": (page_dashboard, ["GET"]),
    "/status": (page_status, ["GET"]),
    "/d/style-test": (page_style_test, ["GET"]),
}
