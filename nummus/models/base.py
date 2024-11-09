"""Base ORM model."""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy
from sqlalchemy import orm, types
from typing_extensions import override

from nummus import exceptions as exc
from nummus import utils
from nummus.models import base_uri

if TYPE_CHECKING:
    from collections.abc import Mapping


# Yield per instead of fetch all is faster
YIELD_PER = 100

ORMBool = orm.Mapped[bool]
ORMBoolOpt = orm.Mapped[bool | None]
ORMInt = orm.Mapped[int]
ORMIntOpt = orm.Mapped[int | None]
ORMStr = orm.Mapped[str]
ORMStrOpt = orm.Mapped[str | None]
ORMReal = orm.Mapped[Decimal]
ORMRealOpt = orm.Mapped[Decimal | None]


class Base(orm.DeclarativeBase):
    """Base ORM model.

    Attributes:
        id_: Primary key identifier, unique
        uri: Uniform Resource Identifier, unique
    """

    @orm.declared_attr  # type: ignore[attr-defined]
    @classmethod
    @override
    def __tablename__(cls) -> str:
        return utils.camel_to_snake(cls.__name__)

    __table_id__: int

    id_: ORMInt = orm.mapped_column(primary_key=True, autoincrement=True)

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

    def __eq__(self, other: Base | object) -> bool:
        """Test equality by URI.

        Args:
            other: Other object to test

        Returns:
            True if URIs match
        """
        return isinstance(other, Base) and self.uri == other.uri

    def __ne__(self, other: Base | object) -> bool:
        """Test inequality by URI.

        Args:
            other: Other object to test

        Returns:
            True if URIs do not match
        """
        return not isinstance(other, Base) or self.uri != other.uri

    @classmethod
    def map_name(cls, s: orm.Session) -> dict[int, str]:
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

    @classmethod
    def validate_strings(cls, key: str, field: str | None) -> str | None:
        """Validates string fields are long enough.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        Raises:
            InvalidORMValueError if field is too short
        """
        if field is None:
            return None
        field = field.strip()
        if field in ["", "[blank]"]:
            return None
        if len(field) < utils.MIN_STR_LEN:
            table: str = cls.__tablename__  # type: ignore[attr-defined]
            table = table.replace("_", " ").capitalize()
            msg = f"{table} {key} must be at least {utils.MIN_STR_LEN} characters long"
            raise exc.InvalidORMValueError(msg)
        return field

    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        """Validates decimals are truncated to their SQL precision.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field
        """
        # Call truncate using the proper Decimal precision
        return getattr(self.__class__, key).type.truncate(field)


class BaseEnum(enum.Enum):
    """Enum class with a parser."""

    @classmethod
    def _missing_(cls, value: object) -> BaseEnum | None:
        if isinstance(value, str):
            s = value.upper().strip().replace(" ", "_")
            if s in cls._member_names_:
                return cls[s]
            return cls._lut().get(s.lower())
        return super()._missing_(value)

    @classmethod
    def _lut(cls) -> Mapping[str, BaseEnum]:
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
    def process_bind_param(
        self,
        value: Decimal | None,
        dialect: sqlalchemy.Dialect,
    ) -> int | None:
        """Receive a bound parameter value to be converted.

        Args:
            value: Python side value to convert
            dialect: Dialect to use

        Returns:
            SQL side representation of value
        """
        if value is None:
            return None
        return int(value * self._FACTOR_IN)

    @override
    def process_result_value(
        self,
        value: int | None,
        dialect: sqlalchemy.Dialect,
    ) -> Decimal | None:
        """Receive a result-row column value to be converted.

        Args:
            value: SQL side value to convert
            dialect: Dialect to use

        Returns:
            Python side representation of value
        """
        if value is None:
            return None
        return Decimal(value) * self._FACTOR_OUT

    @classmethod
    def truncate(cls, value: Decimal | None) -> Decimal | None:
        """Truncate a decimal to the specified precision.

        Args:
            value: Value to truncate

        Returns:
            Decimal -> SQL integer -> Decimal
        """
        if value is None:
            return None
        return Decimal(int(value * cls._FACTOR_IN)) * cls._FACTOR_OUT


class Decimal9(Decimal6):
    """SQL type for fixed point numbers, stores as nano-integer."""

    cache_ok = True

    _FACTOR_OUT = Decimal("1e-9")
    _FACTOR_IN = 1 / _FACTOR_OUT
