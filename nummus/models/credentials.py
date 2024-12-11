"""Credential model for storing a user/password set for a site."""

from __future__ import annotations

from sqlalchemy import orm

from nummus.models.base import Base, ORMStr, string_column_args

# TODO (WattsUp): Remove this model, not used


class Credentials(Base):
    """Credential model for storing a user/password set for a site.

    Attributes:
        site: Name of site credentials belong to
        user: Name of user
        password: Secret password
    """

    __table_id__ = 0x50000000

    site: ORMStr
    user: ORMStr
    password: ORMStr

    __table_args__ = (
        *string_column_args("site"),
        *string_column_args("user"),
        *string_column_args("password"),
    )

    @orm.validates("site", "user", "password")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints."""
        return self.clean_strings(key, field)
