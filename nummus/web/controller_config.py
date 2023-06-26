"""Configuration API controller
"""

from nummus import __version__


def get_version() -> str:
  """GET /api/version

  Returns:
    String response, see api.yaml for details
  """
  return {"api": "0.1.0", "nummus": __version__}
