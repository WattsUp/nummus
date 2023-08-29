"""Web request controllers
"""

import flask

from nummus import custom_types as t
from nummus.controllers import (account, common, dashboard, transaction,
                                transaction_category)


def add_routes(app: flask.Flask) -> None:
  """Add routing table for flask app to appropriate controller

  Args:
    app: Flask app to route under
  """
  all_routes: t.Dict[str, t.Tuple[t.Callable, t.Strings]] = {}
  all_routes.update(account.ROUTES)
  all_routes.update(common.ROUTES)
  all_routes.update(dashboard.ROUTES)
  all_routes.update(transaction.ROUTES)
  all_routes.update(transaction_category.ROUTES)
  for url, item in all_routes.items():
    controller, methods = item
    app.add_url_rule(url, view_func=controller, methods=methods)
