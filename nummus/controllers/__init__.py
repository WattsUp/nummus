"""Web request controllers."""


import flask

from nummus import custom_types as t
from nummus.controllers import (
    account,
    common,
    dashboard,
    transaction,
    transaction_category,
)


def add_routes(app: flask.Flask) -> None:
    """Add routing table for flask app to appropriate controller.

    Args:
        app: Flask app to route under
    """
    module = [
        account,
        common,
        dashboard,
        transaction,
        transaction_category,
    ]
    n_trim = len(__name__) + 1
    for m in module:
        routes: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = getattr(m, "ROUTES")
        for url, item in routes.items():
            controller, methods = item
            endpoint = f"{m.__name__[n_trim:]}.{controller.__name__}"
            app.add_url_rule(url, endpoint, controller, methods=methods)
