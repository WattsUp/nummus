"""Dashboard controllers
"""

import flask


def get_home() -> str:
  """GET /

  Returns:
    string HTML page response
  """
  return flask.render_template("index.html")
