"""Test module nummus.models.base
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, orm

from nummus import custom_types as t
from nummus.models import base

from tests.base import TestBase


class Parent(base.Base):
  """Test Parent class for Base.to_dict, Base.from_dict
  """

  generic_column: t.ORMIntOpt
  name: t.ORMStrOpt
  children: orm.Mapped[t.List[Child]] = orm.relationship(
      back_populates="parent")

  @property
  def favorite_child(self) -> Child:
    """Get the favorite child
    """
    if len(self.children) < 1:
      return None
    return self.children[0]

  @property
  def uuid_bytes(self) -> bytes:
    """Get ID as bytes
    """

    class Bytes:
      """Unserializable class
      """

      def __init__(self, s: str) -> None:
        self._data = s.encode(encoding="utf-8")

      def __eq__(self, other: Bytes) -> bool:
        return self._data == other._data

    return Bytes(self.uuid)


class Child(base.Base):
  """Test Child class for Base.to_dict, Base.from_dict
  """

  parent_id: t.ORMInt = orm.mapped_column(ForeignKey("parent.id"))
  parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")

  height: t.ORMRealOpt = orm.mapped_column(base.Decimal6)


class TestORMBase(TestBase):
  """Test ORM Base
  """

  def test_init_properties(self):
    s = self.get_session()
    base.Base.metadata.create_all(s.get_bind(),
                                  tables=[Parent.__table__, Child.__table__])
    s.commit()

    parent = Parent()
    self.assertIsNone(parent.id)
    self.assertIsNone(parent.uuid)
    s.add(parent)
    s.commit()
    self.assertIsNotNone(parent.id)
    self.assertIsNotNone(parent.uuid)

    child = Child()
    self.assertIsNone(child.id)
    self.assertIsNone(child.uuid)
    self.assertIsNone(child.parent)
    self.assertIsNone(child.parent_id)
    child.parent = parent
    s.add(child)
    s.commit()
    self.assertIsNotNone(child.id)
    self.assertIsNotNone(child.uuid)
    self.assertIsNotNone(child.parent)
    self.assertIsNotNone(child.parent_id)

    child.height = None
    s.commit()
    self.assertIsNone(child.height)

    height = Decimal("1.2")
    child.height = height
    s.commit()
    self.assertIsInstance(child.height, Decimal)
    self.assertEqual(height, child.height)

    # Only 6 decimals
    height = Decimal("1.23456789")
    child.height = height
    s.commit()
    self.assertIsInstance(child.height, Decimal)
    self.assertEqual(Decimal("1.234567"), child.height)

  def test_comparators(self):
    s = self.get_session()
    base.Base.metadata.create_all(s.get_bind(),
                                  tables=[Parent.__table__, Child.__table__])
    s.commit()

    parent_a = Parent()
    parent_b = Parent()
    s.add_all([parent_a, parent_b])
    s.commit()

    self.assertEqual(parent_a, parent_a)
    self.assertNotEqual(parent_a, parent_b)

    # Make a new s to same DB
    with orm.create_session(bind=s.get_bind()) as session_2:
      # Get same parent_a but in a different Python object
      parent_a_queried = session_2.query(Parent).where(
          Parent.id == parent_a.id).first()
      self.assertNotEqual(id(parent_a), id(parent_a_queried))
      self.assertEqual(parent_a, parent_a_queried)

  def test_map_name(self):
    s = self.get_session()
    base.Base.metadata.create_all(s.get_bind(),
                                  tables=[Parent.__table__, Child.__table__])
    s.commit()

    self.assertRaises(KeyError, base.Base.map_name, s)

    parent_a = Parent(name=self.random_string())
    parent_b = Parent(name=self.random_string())
    s.add_all([parent_a, parent_b])
    s.commit()

    result = Parent.map_name(s)
    target = {
        parent_a.id: parent_a.name,
        parent_b.id: parent_b.name,
    }
    self.assertEqual(target, result)

  def test_validate_strings(self):
    parent = Parent()
    key = self.random_string()

    result = parent.validate_strings(key, None)
    self.assertIsNone(result)

    result = parent.validate_strings(key, "")
    self.assertIsNone(result)

    result = parent.validate_strings(key, "[blank]")
    self.assertIsNone(result)

    field = self.random_string(3)
    result = parent.validate_strings(key, field)
    self.assertEqual(field, result)

    self.assertRaises(ValueError, parent.validate_strings, key, "ab")


class Derived(base.BaseEnum):
  """Derived test class for BaseEnum
  """

  RED = 1
  BLUE = 2

  @classmethod
  def _lut(cls) -> t.Dict[str, Derived]:
    return {"r": cls.RED, "b": cls.BLUE}


class TestBaseEnum(TestBase):
  """Test BaseEnum class
  """

  def test_parse(self):
    self.assertEqual(None, Derived.parse(None))
    self.assertEqual(None, Derived.parse(""))

    for e in Derived:
      self.assertEqual(e, Derived.parse(e))
      self.assertEqual(e, Derived.parse(e.name))
      self.assertEqual(e, Derived.parse(e.value))

    for s, e in Derived._lut().items():  # pylint: disable=protected-access
      self.assertEqual(e, Derived.parse(s.upper()))

    self.assertRaises(ValueError, Derived.parse, "FAKE")
