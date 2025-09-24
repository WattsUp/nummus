"""Base ORM model."""

from __future__ import annotations

import enum
from decimal import Decimal
from typing import override, TYPE_CHECKING

import sqlalchemy
from sqlalchemy import CheckConstraint, orm, sql, types

from nummus import exceptions as exc
from nummus import utils
from nummus.models import base_uri

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


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

    __table_id__: int | None

    @classmethod
    def sql_table(cls) -> sqlalchemy.Table:
        """Get the SQL table.

        Returns:
            Table

        Raises:
            TypeError: if __table__ is not a Table

        """
        if isinstance(cls.__table__, sqlalchemy.Table):
            return cls.__table__
        raise TypeError

    id_: ORMInt = orm.mapped_column(primary_key=True, autoincrement=True)

    @classmethod
    def id_to_uri(cls, id_: int) -> str:
        """Uniform Resource Identifier derived from id_ and __table_id__.

        Args:
            id_: Model ID

        Returns:
            URI string

        Raises:
            NoURIError: If class does not have a table_id

        """
        if cls.__table_id__ is None:
            msg = f"{cls.__name__} does not have table_id"
            raise exc.NoURIError(msg)
        return base_uri.id_to_uri(id_ | cls.__table_id__)

    @classmethod
    def uri_to_id(cls, uri: str) -> int:
        """Reverse id_to_uri.

        Args:
            uri: URI string

        Returns:
            Model ID

        Raises:
            WrongURITypeError: If URI does not belong to class

        """
        id_ = base_uri.uri_to_id(uri)
        table_id = id_ & base_uri.MASK_TABLE
        if table_id != cls.__table_id__:
            msg = f"URI did not belong to {cls.__name__}: {uri}"
            raise exc.WrongURITypeError(msg)
        return id_ & base_uri.MASK_ID

    @property
    def uri(self) -> str:
        """Uniform Resource Identifier derived from id_ and __table_id__.

        Raises:
            NoIDError: If object does not have id_

        """
        if self.id_ is None:
            msg = f"{self.__class__.__name__} does not have an id_, maybe flush"
            raise exc.NoIDError(msg)
        return self.id_to_uri(self.id_)

    @override
    def __repr__(self) -> str:
        try:
            return f"<{self.__class__.__name__} id={self.id_}>"
        except orm.exc.DetachedInstanceError:
            return f"<{self.__class__.__name__} id=Detached Instance>"

    @override
    def __hash__(self) -> int:
        return self.id_

    @override
    def __eq__(self, other: Base | object) -> bool:
        return isinstance(other, Base) and self.uri == other.uri

    @override
    def __ne__(self, other: Base | object) -> bool:
        return not isinstance(other, Base) or self.uri != other.uri

    @classmethod
    def map_name(cls, s: orm.Session) -> dict[int, str]:
        """Get mapping between id and names.

        Args:
            s: SQL session to use

        Returns:
            Dictionary {id: name}

        Raises:
            KeyError: if model does not have name property

        """
        attr = getattr(cls, "name", None)
        if not attr:
            msg = f"{cls.__name__} does not have name column"
            raise KeyError(msg)

        query = s.query(cls).with_entities(cls.id_, attr)
        return dict(query.all())

    @classmethod
    def clean_strings(
        cls,
        key: str,
        field: str | None,
        *,
        short_check: bool = True,
    ) -> str | None:
        """Clean and validates string fields.

        Args:
            key: Field being updated
            field: Updated value
            short_check: True will add a check for MIN_STR_LEN

        Returns:
            field

        Raises:
            InvalidORMValueError: if field is too short

        """
        if field is None:
            return None
        field = field.strip()
        if not field:
            return None
        if short_check and len(field) < utils.MIN_STR_LEN:
            table: str = cls.__tablename__
            table = table.replace("_", " ").capitalize()
            msg = f"{table} {key} must be at least {utils.MIN_STR_LEN} characters long"
            raise exc.InvalidORMValueError(msg)
        return field

    @classmethod
    def clean_decimals(cls, key: str, field: Decimal | None) -> Decimal | None:
        """Validate decimals are truncated to their SQL precision.

        Args:
            key: Field being updated
            field: Updated value

        Returns:
            field

        """
        # Call truncate using the proper Decimal precision
        return getattr(cls, key).type.truncate(field)

    @classmethod
    def clean_emoji_name(cls, s: str) -> str:
        """Clean emoji_name into name.

        Args:
            s: String to strip

        Returns:
            s without emojis and in lowercase

        """
        return utils.strip_emojis(s).strip().lower()


class BaseEnum(enum.IntEnum):
    """Enum class with a parser."""

    @classmethod
    def _missing_(cls, value: object) -> BaseEnum | None:
        if isinstance(value, str):
            s = value.upper().strip().replace(" ", "_")
            if s in cls._member_names_:
                return cls[s]
            return cls.lut().get(s.lower())
        return super()._missing_(value)

    @classmethod
    def lut(cls) -> Mapping[str, BaseEnum]:
        """Look up table, mapping of strings to matching Enums.

        Returns:
            Dictionary {alternate names for enums: Enum}

        """
        return {}  # pragma: no cover

    @override
    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return self.name == value
        return super().__eq__(value)

    @override
    def __ne__(self, value: object) -> bool:
        if isinstance(value, str):
            return self.name != value
        return super().__ne__(value)

    @override
    def __hash__(self) -> int:
        return self.value

    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}.{self.name}"

    @property
    def pretty(self) -> str:
        """Prettify enum value."""
        return self.name.replace("_", " ").title()


class SQLEnum(types.TypeDecorator):
    """SQL type for enumeration, stores as integer."""

    impl = types.Integer

    cache_ok = True

    def __init__(
        self,
        enum_type: type[BaseEnum],
        *args: object,
        **kwargs: object,
    ) -> None:
        """Initialize IntEnum.

        Args:
            enum_type: BaseEnum this column is
            args: Passed to super
            kwargs: Passed to super

        """
        super().__init__(*args, **kwargs)

        self._enum_type = enum_type

    @override
    def process_bind_param(
        self,
        value: BaseEnum | None,
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
        return value.value

    @override
    def process_result_value(
        self,
        value: int | None,
        dialect: sqlalchemy.Dialect,
    ) -> BaseEnum | None:
        """Receive a result-row column value to be converted.

        Args:
            value: SQL side value to convert
            dialect: Dialect to use

        Returns:
            Python side representation of value

        """
        if value is None:
            return None
        return self._enum_type(value)


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


def string_column_args(
    name: str,
    *,
    short_check: bool = True,
    lower_check: bool = False,
) -> Iterable[CheckConstraint]:
    """Get table args for string column.

    Args:
        name: Name of string column
        short_check: True will add a check for MIN_STR_LEN
        lower_check: True will add a check for all lower case

    Returns:
        Tuple of constraints

    """
    name_col = f"`{name}`" if name in sql.compiler.RESERVED_WORDS else name
    checks = [
        (
            CheckConstraint(
                f"length({name_col}) >= {utils.MIN_STR_LEN}",
                f"{name} must be at least {utils.MIN_STR_LEN} characters long",
            )
            if short_check
            else CheckConstraint(
                f"{name_col} != ''",
                f"{name} must be empty",
            )
        ),
        CheckConstraint(
            f"{name_col} not like ' %' and {name_col} not like '% '",
            f"{name} must not have leading or trailing whitespace",
        ),
    ]
    if lower_check:
        checks.append(
            CheckConstraint(
                f"{name_col} == lower({name_col})",
                f"{name} must be lower case",
            ),
        )
    return checks
