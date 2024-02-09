"""Credential model for storing a user/password set for a site."""

from __future__ import annotations

from nummus.models.base import Base, ORMStr


class Credentials(Base):
    """Credential model for storing a user/password set for a site.

    Attributes:
        site: Name of site credentials belong to
        user: Name of user
        password: Secret password
    """

    __table_id__ = 0x60000000

    site: ORMStr
    user: ORMStr
    password: ORMStr
