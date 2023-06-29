"""Base ORM model
"""

from __future__ import annotations
from typing import Dict, List, Union, Tuple

import datetime
import enum
import json
import uuid

import sqlalchemy
from sqlalchemy import orm, schema

from nummus import common


class Base(orm.DeclarativeBase):
  """Base ORM model

  Attributes:
    id: Primary key identifier
    uuid: Universally unique identifier
  """
  metadata: schema.MetaData

  _PROPERTIES_DEFAULT: List[str] = ["uuid"]
  _PROPERTIES_HIDDEN: List[str] = ["id"]
  _PROPERTIES_READONLY: List[str] = ["id", "uuid"]

  @orm.declared_attr
  def __tablename__(self):
    return common.camel_to_snake(self.__name__)

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
  # Could be better with storing a uuid as a 16B int but SQLite doesn't have
  # that large of integers
  uuid: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String(36),
                                            default=lambda: str(uuid.uuid4()))

  def __str__(self) -> str:
    return str(self.to_dict())

  def __repr__(self) -> str:
    try:
      return f"<{self.__class__.__name__} id={self.id} uuid={self.uuid}>"
    except orm.exc.DetachedInstanceError:
      return f"<{self.__class__.__name__} id=Detached Instance>"

  def to_dict(
      self,
      show: List[str] = None,
      hide: List[str] = None,
      path: str = None) -> Dict[str, Union[str, float, int, bool, object]]:
    """Return a dictionary representation of this model

    Adds all columns that are not hidden (in hide or in _hidden_properties) and
    shown (in show or in _default_properties)

    Args:
      show: specific properties to add
      hide: specific properties to omit (hide is stronger than show)
      path: path of Model, None uses __tablename__, used for recursion to show
        or hide children properties

    Return:
      Model as a dictionary with columns as keys
    """
    show = [] if show is None else show
    hide = [] if hide is None else hide

    def prepend_path(item: str):
      item = item.lower()
      if item.split(".", 1)[0] == path:
        return item
      if len(item) == 0:
        return item
      if item[0] != ".":
        item = "." + item
      return path + item

    if path is None:
      path = self.__tablename__

      hide = [prepend_path(s) for s in hide]
      show = [prepend_path(s) for s in show]

    attr_show = [prepend_path(s) for s in self._PROPERTIES_DEFAULT]
    attr_hide = [prepend_path(s) for s in self._PROPERTIES_HIDDEN]

    for s in show:
      # Command line is stronger than class
      # Remove shown properties from class hidden
      attr_hide = [a for a in attr_hide if a != s]
      attr_show.append(s)

    for s in hide:
      # Command line is stronger than class
      # Remove shown properties from class hidden
      attr_show = [a for a in attr_show if a != s]
      attr_hide.append(s)

    columns = self.__table__.columns.keys()
    relationships = self.__mapper__.relationships.keys()
    properties = dir(self)

    d = {}

    # Add columns
    for key in columns:
      if key[0] == "_":
        # Private properties are always hidden
        continue
      check = f"{path}.{key}"
      if check in attr_hide or check not in attr_show:
        continue
      d[key] = getattr(self, key)

    # Add relationships recursively
    for key in relationships:
      if key[0] == "_":
        # Private properties are always hidden
        continue
      check = f"{path}.{key}"
      if check in attr_hide or check not in attr_show:
        continue
      hide.append(check)
      is_list = self.__mapper__.relationships[key].uselist
      if is_list:
        items: List[Base] = getattr(self, key)
        l = []
        for item in items:
          item_d = item.to_dict(show=list(show),
                                hide=list(hide),
                                path=f"{path}.{key.lower()}")
          l.append(item_d)
        d[key] = l
      else:
        item = getattr(self, key)
        if item is None:
          d[key] = None
        else:
          item: Base
          d[key] = item.to_dict(show=list(show),
                                hide=list(hide),
                                path=f"{path}.{key.lower()}")

    # Get any stragglers (@property and QueryableAttribute)
    for key in list(set(properties) - set(columns) - set(relationships)):
      if key[0] == "_":
        # Private properties are always hidden
        continue
      if not hasattr(self.__class__, key):
        continue
      attr = getattr(self.__class__, key)
      if not isinstance(attr, (property, orm.QueryableAttribute)):
        continue
      check = f"{path}.{key}"
      if check in attr_hide or check not in attr_show:
        continue
      item = getattr(self, key)
      if hasattr(item, "to_dict"):
        item: Base
        d[key] = item.to_dict(show=list(show),
                              hide=list(hide),
                              path=f"{path}.{key.lower()}")
      else:
        d[key] = json.loads(json.dumps(item, cls=NummusJSONEncoder))

    return d

  def update(self,
             data: Dict[str, Union[str, float, int, bool, object]],
             force: bool = False) -> Dict[str, Tuple[object, object]]:
    """Update model from dictionary

    Only updates columns

    Args:
      data: Dictionary to update properties from
      force: True will overwrite readonly properties

    Returns:
      Dictionary of changes {attribute: (old, new)}
    """
    attr_readonly = self._PROPERTIES_READONLY + self._PROPERTIES_HIDDEN

    columns = self.__table__.columns.keys()
    relationships = self.__mapper__.relationships.keys()
    properties = dir(self)

    changes: Dict[str, Tuple[object, object]] = {}

    # Update columns
    for key in columns:
      if key[0] == "_":
        # Private properties are always readonly
        continue
      if (key not in data) or (not force and key in attr_readonly):
        continue
      val_old = getattr(self, key)
      val_new = data[key]
      if val_old != val_new:
        changes[key] = (val_old, val_new)
        setattr(self, key, val_new)

    # Don't update relationships
    # Force the user to update via the governing id columns
    # Aka parent_id = new_parent.id not parent = new_parent

    # Update properties
    for key in list(set(properties) - set(columns) - set(relationships)):
      if key[0] == "_":
        # Private properties are always readonly
        continue
      if (key not in data) or (not force and key in attr_readonly):
        continue
      if getattr(self.__class__, key).fset is None:
        # No setter, skip
        continue
      val_old = getattr(self, key)
      val_new = data[key]
      if val_old != val_new:
        changes[key] = (val_old, val_new)
        setattr(self, key, val_new)

    return changes

  def __eq__(self, other: Base) -> bool:
    """Test equality by UUID

    Args:
      other: Other object to test

    Returns:
      True if UUIDs match
    """
    return self.uuid == other.uuid

  def __ne__(self, other: Base) -> bool:
    """Test inequality by UUID

    Args:
      other: Other object to test

    Returns:
      True if UUIDs do not match
    """
    return self.uuid != other.uuid


class NummusJSONEncoder(json.JSONEncoder):
  """Custom JSON Encoder for nummus models
  """

  def default(self, o: object) -> object:
    if isinstance(o, Base):
      return o.to_dict()
    if isinstance(o, enum.Enum):
      return o.name.lower()
    if isinstance(o, datetime.date):
      return o.isoformat()
    return super().default(o)


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
    r = cls._lut().get(s)
    if r is None:
      raise ValueError(f"String not found in {cls.__name__}: {s}")
    return r

  @classmethod
  def _lut(cls) -> Dict[str, BaseEnum]:
    """Look up table, mapping of strings to matching Enums

    Returns:
      Dictionary {alternate names for enums: Enum}
    """
    return {}
