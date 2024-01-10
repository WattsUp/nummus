"""Config model for storing a key/value pair."""

from __future__ import annotations

from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base


class Config(Base):
    """Config model for storing a key/value pair.

    Attributes:
        key: Key of config pair
        value: Value of config pair
    """

    # No __table_id__ because this is not user accessible

    key: t.ORMStr = orm.mapped_column(unique=True)
    value: t.ORMStr
