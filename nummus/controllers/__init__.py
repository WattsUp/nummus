"""Web request controllers
"""

import flask

from nummus import custom_types as t
from nummus.controllers import accounts, common, dashboard, transactions

ROUTES: t.Dict[str, t.Callable] = {
    "/": (dashboard.page_home, ["GET"]),
    "/index": (dashboard.page_home, ["GET"]),
    "/h/sidebar": (common.sidebar, ["GET"]),
    "/transactions": (transactions.page_all, ["GET"]),
    "/transactions/<path:path_uuid>": (transactions.page_one, ["GET"]),
    "/h/accounts/<path:path_uuid>/edit":
        (accounts.edit_account, ["GET", "POST"]),
    "/h/none": (lambda: "", ["GET"])
}


def add_routes(app: flask.Flask) -> None:
  """Add routing table for flask app to appropriate controller

  Args:
    app: Flask app to route under
  """
  for url, item in ROUTES.items():
    controller, methods = item
    app.add_url_rule(url, view_func=controller, methods=methods)
