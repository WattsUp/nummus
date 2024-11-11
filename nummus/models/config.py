"""Config model for storing a key/value pair."""

from __future__ import annotations

from sqlalchemy import orm

from nummus.models.base import Base, BaseEnum, ORMStr, SQLEnum, string_column_args


class ConfigKey(BaseEnum):
    """Configuration keys."""

    VERSION = 1
    ENCRYPTION_TEST = 2
    CIPHER = 3
    SECRET_KEY = 4


class Config(Base):
    """Config model for storing a key/value pair.

    Attributes:
        key: Key of config pair
        value: Value of config pair
    """

    # No __table_id__ because this is not user accessible

    key: orm.Mapped[ConfigKey] = orm.mapped_column(SQLEnum(ConfigKey), unique=True)
    value: ORMStr

    __table_args__ = (*string_column_args("value"),)

    @orm.validates("value")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints."""
        return self.clean_strings(key, field)
