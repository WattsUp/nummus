"""Credential model for storing a user/password set for a site."""

from __future__ import annotations

from nummus import custom_types as t
from nummus.models.base import Base


class Credentials(Base):
    """Credential model for storing a user/password set for a site.

    Attributes:
        site: Name of site credentials belong to
        user: Name of user
        password: Secret password
    """

    site: t.ORMStr
    user: t.ORMStr
    password: t.ORMStr
