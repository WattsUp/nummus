"""Credential model for storing a user/password set for a site
"""

from sqlalchemy import orm

from nummus.models import base


class Credentials(base.Base):
  """Credential model for storing a user/password set for a site

  Attributes:
    site: Name of site credentials belong to
    user: Name of user
    password: Secret password
  """

  _PROPERTIES_DEFAULT = ["id", "site", "user"]
  _PROPERTIES_HIDDEN = ["password"]

  site: orm.Mapped[str]
  user: orm.Mapped[str]
  password: orm.Mapped[str]
