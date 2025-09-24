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
    WEB_KEY = 5
    LAST_HEALTH_CHECK_TS = 6


class Config(Base):
    """Config model for storing a key/value pair.

    Attributes:
        key: Key of config pair
        value: Value of config pair

    """

    __tablename__ = "config"
    __table_id__ = None

    key: orm.Mapped[ConfigKey] = orm.mapped_column(SQLEnum(ConfigKey), unique=True)
    value: ORMStr

    __table_args__ = (*string_column_args("value"),)

    @orm.validates("value")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validate string fields satisfy constraints.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        return self.clean_strings(key, field)
