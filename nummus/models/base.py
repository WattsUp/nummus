"""Base ORM model."""

from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import orm, types
from typing_extensions import override

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import utils
from nummus.models import base_uri

# Yield per instead of fetch all is faster
YIELD_PER = 100


class Base(orm.DeclarativeBase):
    """Base ORM model.

    Attributes:
        id_: Primary key identifier, unique
        uri: Uniform Resource Identifier, unique
    """

    @orm.declared_attr  # type: ignore[attr-defined]
    @override
    def __tablename__(self) -> str:
        return utils.camel_to_snake(self.__name__)

    __table_id__: int

    id_: t.ORMInt = orm.mapped_column(primary_key=True, autoincrement=True)

    @classmethod
    def id_to_uri(cls, id_: int) -> str:
        """Uniform Resource Identifier derived from id_ and __table_id__.

        Args:
            id_: Model ID

        Returns:
            URI string
        """
        return base_uri.id_to_uri(id_ | cls.__table_id__)

    @classmethod
    def uri_to_id(cls, uri: str) -> int:
        """Reverse id_to_uri.

        Args:
            uri: URI string

        Returns:
            Model ID
        """
        id_ = base_uri.uri_to_id(uri)
        table_id = id_ & base_uri.MASK_TABLE
        if table_id != cls.__table_id__:
            msg = f"URI did not belong to {cls.__name__}: {uri}"
            raise exc.WrongURITypeError(msg)
        return id_ & base_uri.MASK_ID

    @property
    def uri(self) -> str:
        """Uniform Resource Identifier derived from id_ and __table_id__."""
        return self.id_to_uri(self.id_)

    @override
    def __repr__(self) -> str:
        try:
            return f"<{self.__class__.__name__} id={self.id_}>"
        except orm.exc.DetachedInstanceError:
            return f"<{self.__class__.__name__} id=Detached Instance>"

    def __eq__(self, other: Base | t.Any) -> bool:
        """Test equality by URI.

        Args:
            other: Other object to test

        Returns:
            True if URIs match
        """
        return isinstance(other, Base) and self.uri == other.uri

    def __ne__(self, other: Base | t.Any) -> bool:
        """Test inequality by URI.

        Args:
            other: Other object to test

        Returns:
            True if URIs do not match
        """
        return not isinstance(other, Base) or self.uri != other.uri

    @classmethod
    def map_name(cls, s: orm.Session) -> t.DictIntStr:
        """Mapping between id and names.

        Args:
            s: SQL session to use

        Returns:
            Dictionary {id: name}

        Raises:
            KeyError if model does not have name property
        """
        if not hasattr(cls, "name"):
            msg = f"{cls} does not have name column"
            raise KeyError(msg)

        query = s.query(cls).with_entities(cls.id_, cls.name)  # type: ignore[attr-defined]
        return dict(query.all())

    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields are not empty.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError if field is empty
        """
        if field is None or field in ["", "[blank]"]:
            return None
        if len(field) < utils.MIN_STR_LEN:
            table: str = self.__tablename__
            table = table.replace("_", " ").capitalize()
            msg = f"{table} {key} must be at least {utils.MIN_STR_LEN} characters long"
            raise exc.InvalidORMValueError(msg)
        return field


class BaseEnum(enum.Enum):
    """Enum class with a parser."""

    @classmethod
    def _missing_(cls, value: object) -> BaseEnum | None:
        if isinstance(value, str):
            s = value.upper().strip()
            if s in cls._member_names_:
                return cls[s]
            return cls._lut().get(s.lower())
        return super()._missing_(value)

    @classmethod
    def _lut(cls) -> t.Mapping[str, BaseEnum]:
        """Look up table, mapping of strings to matching Enums.

        Returns:
            Dictionary {alternate names for enums: Enum}
        """
        return {}  # pragma: no cover


class Decimal6(types.TypeDecorator):
    """SQL type for fixed point numbers, stores as micro-integer."""

    impl = types.BigInteger

    cache_ok = True

    _FACTOR_OUT = Decimal("1e-6")
    _FACTOR_IN = 1 / _FACTOR_OUT

    @override
    def process_bind_param(self, value: t.Real | None, *_) -> int | None:
        """Receive a bound parameter value to be converted.

        Args:
            value: Python side value to convert

        Returns:
            SQL side representation of value
        """
        if value is None:
            return None
        return int(value * self._FACTOR_IN)

    @override
    def process_result_value(self, value: int | None, *_) -> t.Real | None:
        """Receive a result-row column value to be converted.

        Args:
            value: SQL side value to convert

        Returns:
            Python side representation of value
        """
        if value is None:
            return None
        return Decimal(value) * self._FACTOR_OUT


class Decimal18(Decimal6):
    """SQL type for fixed point numbers, stores as atto-integer."""

    cache_ok = True

    _FACTOR_OUT = Decimal("1e-18")
    _FACTOR_IN = 1 / _FACTOR_OUT
