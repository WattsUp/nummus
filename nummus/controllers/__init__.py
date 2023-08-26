"""Web request controllers
"""

import flask

from nummus import custom_types as t
from nummus.controllers import accounts, common, dashboard, transactions

ROUTES: t.Dict[str, t.Callable] = {
    "/": dashboard.page_home,
    "/index": dashboard.page_home,
    "/transactions": transactions.page_all,
    "/transactions/<path:path_uuid>": transactions.page_one,
    "/h/accounts/<path:path_uuid>/edit": accounts.edit_account,
    "/h/overlay-none": common.overlay_none
}


def add_routes(app: flask.Flask) -> None:
  """Add routing table for flask app to appropriate controller

  Args:
    app: Flask app to route under
  """
  for url, controller in ROUTES.items():
    app.add_url_rule(url, view_func=controller)
