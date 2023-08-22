"""Dashboard controllers
"""

import flask


def page_home() -> str:
  """GET /

  Returns:
    string HTML response
  """
  return flask.render_template("index.html")
