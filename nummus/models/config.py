"""Config model for storing a key/value pair."""

from __future__ import annotations

from typing import Literal, overload

from packaging.version import Version
from sqlalchemy import orm

from nummus import exceptions as exc
from nummus.models.base import Base, BaseEnum, ORMStr, SQLEnum, string_column_args
from nummus.models.currency import Currency


class ConfigKey(BaseEnum):
    """Configuration keys."""

    VERSION = 1
    ENCRYPTION_TEST = 2
    CIPHER = 3
    SECRET_KEY = 4
    WEB_KEY = 5
    LAST_HEALTH_CHECK_TS = 6
    BASE_CURRENCY = 7


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

    @classmethod
    def set_(cls, s: orm.Session, key: ConfigKey, value: str) -> None:
        """Set a Configuration value.

        Args:
            s: SQL session to use
            key: ConfigKey to query
            value: Value to set

        """
        if s.query(Config).where(Config.key == key).update({"value": value}):
            return
        s.add(Config(key=key, value=value))

    @overload
    @classmethod
    def fetch(
        cls,
        s: orm.Session,
        key: ConfigKey,
        *,
        no_raise: Literal[False] = False,
    ) -> str: ...

    @overload
    @classmethod
    def fetch(
        cls,
        s: orm.Session,
        key: ConfigKey,
        *,
        no_raise: Literal[True],
    ) -> str | None: ...

    @classmethod
    def fetch(
        cls,
        s: orm.Session,
        key: ConfigKey,
        *,
        no_raise: bool = False,
    ) -> str | None:
        """Fetch a Configuration value.

        Args:
            s: SQL session to use
            key: ConfigKey to query
            no_raise: True will return None if missing

        Returns:
            string value

        Raises:
            ProtectedObjectNotFoundError: If key is not found

        """
        try:
            return s.query(Config.value).where(Config.key == key).one()[0]
        except exc.NoResultFound as e:
            if no_raise:
                return None
            msg = f"Config.{key} not found"
            raise exc.ProtectedObjectNotFoundError(msg) from e

    @classmethod
    def db_version(cls, s: orm.Session) -> Version:
        """Query the database version.

        Args:
            s: SQL session to use

        Returns:
            Version of database

        """
        return Version(Config.fetch(s, ConfigKey.VERSION))

    @classmethod
    def base_currency(cls, s: orm.Session) -> Currency:
        """Query the basse currency.

        Args:
            s: SQL session to use

        Returns:
            Base currency all accounts are converted into

        """
        return Currency(int(Config.fetch(s, ConfigKey.BASE_CURRENCY)))
