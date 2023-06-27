"""Configuration API controller
"""

import flask

from nummus import __version__


def get_version() -> flask.Response:
  """GET /api/version

  Returns:
    JSON response, see api.yaml for details
  """
  return flask.jsonify({"api": "0.1.0", "nummus": __version__})
