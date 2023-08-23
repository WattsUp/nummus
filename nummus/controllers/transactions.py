"""Transaction controllers
"""

import flask

from nummus.controllers import common


def page_all() -> str:
  """GET /transactions

  Returns:
    string HTML response
  """
  return flask.render_template("transactions.html", sidebar=common.sidebar())
