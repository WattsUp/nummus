"""Web request controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import exceptions as exc
from nummus.controllers import (
    accounts,
    allocation,
    assets,
    auth,
    budgeting,
    common,
    dashboard,
    emergency_fund,
    health,
    import_file,
    transaction_categories,
    transactions,
)

if TYPE_CHECKING:
    import flask

    from nummus.controllers.base import Routes


def add_routes(app: flask.Flask, *, debug: bool) -> None:
    """Add routing table for flask app to appropriate controller.

    Args:
        app: Flask app to route under
        debug: True will add debug specific routes as well

    Raises:
        DuplicateURLError: If multiple routes have same URL
    """
    module = [
        accounts,
        allocation,
        assets,
        auth,
        budgeting,
        common,
        dashboard,
        emergency_fund,
        health,
        import_file,
        transactions,
        transaction_categories,
    ]
    n_trim = len(__name__) + 1
    urls: set[str] = set()
    for m in module:
        routes: Routes = m.ROUTES
        for url, (controller, methods) in routes.items():
            endpoint = f"{m.__name__[n_trim:]}.{controller.__name__}"
            if url in urls:  # pragma: no cover
                raise exc.DuplicateURLError(url, endpoint)
            if url.startswith("/d/") and not debug:
                continue
            urls.add(url)
            app.add_url_rule(url, endpoint, controller, methods=methods)
