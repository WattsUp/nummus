"""Transaction controllers
"""

import flask


def page_all() -> str:
  """GET /transactions

  Returns:
    string HTML response
  """
  return flask.render_template("transactions.html")
