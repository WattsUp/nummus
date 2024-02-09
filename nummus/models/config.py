"""Config model for storing a key/value pair."""

from __future__ import annotations

from sqlalchemy import orm

from nummus.models.base import Base, BaseEnum, ORMStr


class ConfigKey(BaseEnum):
    """Configuration keys."""

    VERSION = 1
    ENCRYPTION_TEST = 2
    CIPHER = 3


class Config(Base):
    """Config model for storing a key/value pair.

    Attributes:
        key: Key of config pair
        value: Value of config pair
    """

    # No __table_id__ because this is not user accessible

    key: orm.Mapped[ConfigKey] = orm.mapped_column(unique=True)
    value: ORMStr
