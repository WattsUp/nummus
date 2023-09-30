"""Base ORM model
"""

from __future__ import annotations

from decimal import Decimal
import enum
import uuid

import sqlalchemy
from sqlalchemy import orm, schema, types

from nummus import common
from nummus import custom_types as t


class Base(orm.DeclarativeBase):
  """Base ORM model

  Attributes:
    id: Primary key identifier
    uuid: Universally unique identifier
  """
  metadata: schema.MetaData

  @orm.declared_attr
  def __tablename__(self) -> str:
    return common.camel_to_snake(self.__name__)

  id: t.ORMInt = orm.mapped_column(primary_key=True, autoincrement=True)

  # Could be better with storing a uuid as a 16B int but SQLite doesn't have
  # that large of integers
  uuid: t.ORMStr = orm.mapped_column(sqlalchemy.String(36),
                                     default=lambda: str(uuid.uuid4()))

  def __repr__(self) -> str:
    try:
      return f"<{self.__class__.__name__} id={self.id} uuid={self.uuid}>"
    except orm.exc.DetachedInstanceError:
      return f"<{self.__class__.__name__} id=Detached Instance>"

  def __eq__(self, other: Base) -> bool:
    """Test equality by UUID

    Args:
      other: Other object to test

    Returns:
      True if UUIDs match
    """
    return other is not None and self.uuid == other.uuid

  def __ne__(self, other: Base) -> bool:
    """Test inequality by UUID

    Args:
      other: Other object to test

    Returns:
      True if UUIDs do not match
    """
    return other is None or self.uuid != other.uuid

  @classmethod
  def map_uuid(cls, s: orm.Session) -> t.DictIntStr:
    """Mapping between id and uuid

    Args:
      s: SQL session to use

    Returns:
      Dictionary {id: uuid}
    """
    query = s.query(cls)
    query = query.with_entities(cls.id, cls.uuid)
    return dict(query.all())

  @classmethod
  def map_name(cls, s: orm.Session) -> t.DictIntStr:
    """Mapping between id and names

    Args:
      s: SQL session to use

    Returns:
      Dictionary {id: name}

    Raises:
      KeyError if model does not have name property
    """
    if not hasattr(cls, "name"):
      raise KeyError(f"{cls} does not have name column")

    query = s.query(cls)
    query = query.with_entities(cls.id, cls.name)
    return dict(query.all())


class BaseEnum(enum.Enum):
  """Enum class with a parser
  """

  @classmethod
  def parse(cls, s: str) -> BaseEnum:
    """Parse a string and return matching enum

    Args:
      s: String to parse

    Returns:
      BaseEnum enumeration that matches
    """
    if isinstance(s, cls):
      return s
    if isinstance(s, int):
      return cls(s)
    if s in ["", None]:
      return None
    s = s.upper().strip()
    if s in cls._member_names_:
      return cls[s]

    s = s.lower()
    # LUT of common strings to the matching enum
    res = cls._lut().get(s)
    if res is None:
      raise ValueError(f"String not found in {cls.__name__}: {s}")
    return res

  @classmethod
  def _lut(cls) -> t.Dict[str, BaseEnum]:
    """Look up table, mapping of strings to matching Enums

    Returns:
      Dictionary {alternate names for enums: Enum}
    """
    return {}  # pragma: no cover


class Decimal6(types.TypeDecorator):
  """SQL type for fixed point numbers, stores as micro-integer
  """

  impl = types.BigInteger

  cache_ok = True

  _FACTOR = Decimal("1e6")

  def process_bind_param(self, value: t.Real, _) -> int:
    """Receive a bound parameter value to be converted

    Args:
      value: Python side value to convert

    Returns:
      SQL side representation of value
    """
    if value is None:
      return None
    return int(value * self._FACTOR)

  def process_result_value(self, value: int, _) -> t.Real:
    """Receive a result-row column value to be converted

    Args:
      value: SQL side value to convert

    Returns:
      Python side representation of value
    """
    if value is None:
      return None
    return Decimal(value) / self._FACTOR


class Decimal18(Decimal6):
  """SQL type for fixed point numbers, stores as atto-integer
  """

  cache_ok = True

  _FACTOR = Decimal("1e18")
