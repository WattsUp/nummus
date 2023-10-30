"""Web request controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import (
    accounts,
    common,
    dashboard,
    net_worth,
    transaction_categories,
    transactions,
)

if TYPE_CHECKING:
    import flask

    from nummus import custom_types as t


def add_routes(app: flask.Flask) -> None:
    """Add routing table for flask app to appropriate controller.

    Args:
        app: Flask app to route under
    """
    module = [
        accounts,
        common,
        dashboard,
        net_worth,
        transactions,
        transaction_categories,
    ]
    n_trim = len(__name__) + 1
    for m in module:
        routes: t.Routes = m.ROUTES
        for url, item in routes.items():
            controller, methods = item
            endpoint = f"{m.__name__[n_trim:]}.{controller.__name__}"
            app.add_url_rule(url, endpoint, controller, methods=methods)
