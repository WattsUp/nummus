"""Dashboard controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import common

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


def page() -> str:
    """GET /.

    Returns:
        string HTML response
    """
    return common.page("index-content.jinja", title="Dashboard | nummus")


ROUTES: Routes = {
    "/": (page, ["GET"]),
    "/index": (page, ["GET"]),
}
