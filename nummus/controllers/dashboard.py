"""Dashboard controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING


from nummus.controllers import common

if TYPE_CHECKING:
    from nummus import custom_types as t


def page_home() -> str:
    """GET /.

    Returns:
        string HTML response
    """
    return common.page("index-content.jinja")


ROUTES: t.Routes = {
    "/": (page_home, ["GET"]),
    "/index": (page_home, ["GET"]),
}
