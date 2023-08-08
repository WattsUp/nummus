"""Web controllers for HTML pages
"""

import flask


def get_home() -> str:
  """GET /

  Returns:
    string HTML page response
  """
  # TODO (WattsUp) Add env like version info to footer
  return flask.render_template("index.html")
