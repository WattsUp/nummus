"""Web request controllers
"""

import types

import flask

from nummus import custom_types as t
from nummus.controllers import (account, common, dashboard, transaction,
                                transaction_category)


def add_routes(app: flask.Flask) -> None:
  """Add routing table for flask app to appropriate controller

  Args:
    app: Flask app to route under
  """
  n_trim = len(__name__) + 1
  for v in globals().values():
    if not isinstance(v, types.ModuleType):
      continue
    if not v.__name__.startswith(__name__):
      continue
    routes: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = getattr(v, "ROUTES")
    if routes is None:
      continue
    for url, item in routes.items():
      controller, methods = item
      endpoint = f"{v.__name__[n_trim:]}.{controller.__name__}"
      app.add_url_rule(url, endpoint, controller, methods=methods)
