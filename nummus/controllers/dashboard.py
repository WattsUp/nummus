"""Dashboard controllers
"""

import flask

from nummus.controllers import common


def page_home() -> str:
  """GET /

  Returns:
    string HTML response
  """
  return flask.render_template("index.html", sidebar=common.sidebar())
