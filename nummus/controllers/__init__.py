"""Web request controllers
"""

import flask

from nummus import custom_types as t
from nummus.controllers import common, dashboard

ROUTES: t.Dict[str, t.Callable] = {
    "/": dashboard.get_home,
    "/index": dashboard.get_home,
    "/c/sidebar": common.get_sidebar
}


def add_routes(app: flask.Flask) -> None:
  """Add routing table for flask app to appropriate controller

  Args:
    app: Flask app to route under
  """
  for url, controller in ROUTES.items():
    app.add_url_rule(url, view_func=controller)
