"""Test module nummus.models.base
"""

from __future__ import annotations

import datetime
from decimal import Decimal
import json
import uuid

from sqlalchemy import ForeignKey, orm

from nummus import models
from nummus import custom_types as t
from nummus.models import base

from tests.base import TestBase


class ClassType(base.BaseEnum):
  """Test enum class for NummusJSONEncoder
  """

  CHILD = 0
  PARENT = 1


class Parent(base.Base):
  """Test Parent class for Base.to_dict, Base.from_dict
  """

  _PROPERTIES_HIDDEN = ["age"]

  _hidden_column: t.ORMIntOpt
  generic_column: t.ORMIntOpt
  children: orm.Mapped[t.List[Child]] = orm.relationship(
      back_populates="parent")

  _age = 40

  @property
  def age(self) -> int:
    """Age of parent in years
    """
    return self._age

  @age.setter
  def age(self, age: int) -> None:
    self._age = age

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


class ParentHidden(base.Base):
  """Test Parent class for Base.to_dict, Base.from_dict with hidden properties
  """

  _PROPERTIES_HIDDEN = ["generic_column"]

  _hidden_column: t.ORMIntOpt
  generic_column: t.ORMIntOpt
  _children: orm.Mapped[t.List[Child]] = orm.relationship(
      back_populates="parent_hidden")

  _age = 43

  @property
  def age(self) -> int:
    """Age of parent in years
    """
    return self._age

  @age.setter
  def age(self, age: int) -> None:
    self._age = age


class Child(base.Base):
  """Test Child class for Base.to_dict, Base.from_dict
  """

  _PROPERTIES_DEFAULT = ["uuid", "age"]

  _hidden_column: t.ORMIntOpt
  parent_id: t.ORMInt = orm.mapped_column(ForeignKey("parent.id"))
  parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")
  parent_hidden_id: t.ORMIntOpt = orm.mapped_column(
      ForeignKey("parent_hidden.id"))
  parent_hidden: orm.Mapped[ParentHidden] = orm.relationship(
      back_populates="_children")

  height: t.ORMRealOpt = orm.mapped_column(base.Decimal6)

  _age = 10

  @property
  def age(self) -> int:
    """Age of Child in years
    """
    return self._age

  @age.setter
  def age(self, age: int) -> None:
    self._age = age


class TestORMBase(TestBase):
  """Test ORM Base
  """

  def test_init_properties(self):
    s = self.get_session()
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
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
    self.assertIsNone(child.parent_hidden)
    self.assertIsNone(child.parent_hidden_id)
    child.parent = parent
    s.add(child)
    s.commit()
    self.assertIsNotNone(child.id)
    self.assertIsNotNone(child.uuid)
    self.assertIsNotNone(child.parent)
    self.assertIsNotNone(child.parent_id)
    self.assertIsNone(child.parent_hidden)
    self.assertIsNone(child.parent_hidden_id)

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

  def test_to_dict(self):
    s = self.get_session()
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    s.commit()

    parent = Parent()
    parent_hidden = ParentHidden()
    s.add_all([parent, parent_hidden])
    s.commit()

    child = Child(parent_id=parent.id)
    child.not_a_class_property = None
    s.add(child)
    s.commit()

    target = {"uuid": child.uuid, "age": child.age}
    d = child.to_dict()
    self.assertDictEqual(target, d)
    self.assertEqual(str(target), str(child))
    d = child.to_dict(hide=[""])  # Empty string ignored
    self.assertDictEqual(target, d)
    self.assertEqual(str(target), str(child))

    # Hide is stronger
    target = {"age": child.age, "parent_hidden": None}
    d = child.to_dict(hide=["uuid"], show=["uuid", "parent_hidden"])
    self.assertDictEqual(target, d)

    # Hide uuid but child is at Parent.Child
    target = {"uuid": child.uuid, "age": child.age}
    d = child.to_dict(hide=["uuid"],
                      path=f"{Parent.__tablename__}.{Child.__tablename__}")
    self.assertDictEqual(target, d)

    # Hide uuid in other ways
    target = {"age": child.age}
    d = child.to_dict(hide=[f"{Child.__tablename__}.uuid"])
    self.assertDictEqual(target, d)

    target = {"age": child.age}
    d = child.to_dict(hide=[".uuid"])
    self.assertDictEqual(target, d)

    # Test default Parent
    target = {"uuid": parent.uuid}
    d = parent.to_dict()
    self.assertDictEqual(target, d)

    target = {"uuid": parent_hidden.uuid}
    d = parent_hidden.to_dict()
    self.assertDictEqual(target, d)

    # Add a non-default property
    child.parent_hidden = parent_hidden
    s.commit()

    target = {
        "uuid": child.uuid,
        "parent_id": parent.id,
        "parent": {
            "uuid": parent.uuid
        },
        "parent_hidden": {
            "uuid": parent_hidden.uuid
        }
    }
    d = child.to_dict(show=["parent", "parent_id", "parent_hidden"],
                      hide=["age"])
    self.assertDictEqual(target, d)

    # Test non-serializable objects
    self.assertRaises(TypeError, parent.to_dict, show=["uuid_bytes"])

    # Test recursion and non-serializable objects
    target = {
        "uuid": parent.uuid,
        "children": [{
            "uuid": child.uuid,
            "age": child.age
        }],
        "favorite_child": {
            "uuid": child.uuid,
            "age": child.age
        }
    }
    d = parent.to_dict(show=["children", "favorite_child"])
    self.assertDictEqual(target, d)

    # Test recursion show/hiding
    target = {
        "uuid": parent.uuid,
        "age": parent.age,
        "children": [{
            "uuid": child.uuid
        }]
    }
    d = parent.to_dict(show=["children", "age"], hide=["children.age"])
    self.assertDictEqual(target, d)

    # Hide a relationship
    target = {"uuid": parent.uuid}
    d = parent.to_dict(hide=["children"])
    self.assertDictEqual(target, d)

    # Check hidden relationship is hidden
    target = {"uuid": parent_hidden.uuid}
    d = parent_hidden.to_dict()
    self.assertDictEqual(target, d)

    # Check hidden relationship is not shown when asked
    target = {"uuid": parent_hidden.uuid}
    d = parent_hidden.to_dict(show=["_children"])
    self.assertDictEqual(target, d)

  def test_update(self):
    s = self.get_session()
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    s.commit()

    parent_a = Parent()
    parent_b = Parent()
    s.add_all([parent_a, parent_b])
    s.commit()

    d = {
        "id": int(self._RNG.integers(10, 1000)),
        "uuid": str(uuid.uuid4()),
        "age": int(self._RNG.integers(50, 100))
    }

    child_a = Child(parent=parent_a)
    child_b = Child(parent=parent_b)
    s.add_all([child_a, child_b])
    s.commit()

    self.assertEqual(1, len(parent_a.children))
    self.assertEqual(1, len(parent_b.children))

    id_old = child_a.id
    uuid_old = child_a.uuid
    age_old = child_a.age
    changes = child_a.update(d, force=False)
    s.commit()
    self.assertEqual(id_old, child_a.id)  # id is readonly
    self.assertEqual(uuid_old, child_a.uuid)  # uuid is readonly
    self.assertEqual(d["age"], child_a.age)
    self.assertDictEqual({"age": (age_old, d["age"])}, changes)

    # age is the same, not updated
    changes = child_a.update(d, force=True)
    s.commit()
    self.assertEqual(d["id"], child_a.id)
    self.assertEqual(d["uuid"], child_a.uuid)
    self.assertEqual(d["age"], child_a.age)
    self.assertDictEqual(
        {
            "id": (id_old, d["id"]),
            "uuid": (uuid_old, d["uuid"])
        }, changes)

    # Both are the same, not updated
    changes = child_a.update(d, force=True)
    s.commit()
    self.assertEqual(d["age"], child_a.age)
    self.assertEqual(d["id"], child_a.id)
    self.assertEqual(d["uuid"], child_a.uuid)
    self.assertDictEqual({}, changes)

    # Update parent via id
    d = {"parent_id": parent_b.id}
    changes = child_a.update(d)
    s.commit()
    self.assertEqual(parent_b, child_a.parent)
    self.assertDictEqual({"parent_id": (parent_a.id, parent_b.id)}, changes)

    self.assertEqual(0, len(parent_a.children))
    self.assertEqual(2, len(parent_b.children))

    # Can't update relationships by obj
    d = {"parent": parent_a}
    changes = child_a.update(d)
    s.commit()
    self.assertEqual(parent_b, child_a.parent)
    self.assertEqual(parent_b.id, child_a.parent_id)
    self.assertDictEqual({}, changes)

    self.assertEqual(0, len(parent_a.children))
    self.assertEqual(2, len(parent_b.children))

    d = {"children": []}
    changes = parent_a.update(d)
    s.commit()
    self.assertEqual(parent_b, child_a.parent)
    self.assertDictEqual({}, changes)

    self.assertEqual(0, len(parent_a.children))
    self.assertEqual(2, len(parent_b.children))

    # Changing IDs is forcible but will cause IntegrityErrors upon execution
    id_old = parent_b.id
    d = {"id": str(uuid.uuid4())}
    changes = parent_b.update(d, force=True)
    self.assertRaises(models.exc.IntegrityError, s.commit)
    s.rollback()

    # Revert
    d = {"id": id_old}
    _ = parent_b.update(d, force=True)
    s.commit()
    self.assertEqual(id_old, parent_b.id)
    self.assertEqual(id_old, child_a.parent_id)
    self.assertEqual(parent_b, child_a.parent)

    d = {"id": id_old}

    # Hidden property will not update
    age_old = parent_b.age
    d = {"age": self._RNG.integers(50, 100)}
    changes = parent_b.update(d)
    s.commit()
    self.assertEqual(age_old, parent_b.age)
    self.assertDictEqual({}, changes)

    changes = parent_b.update(d, force=True)
    s.commit()
    self.assertEqual(d["age"], parent_b.age)
    self.assertDictEqual({"age": (age_old, d["age"])}, changes)

    # Property without a setter will not update
    uuid_bytes_old = parent_b.uuid_bytes
    d = {"uuid_bytes": str(uuid.uuid4()).encode()}
    changes = parent_b.update(d)
    s.commit()
    self.assertEqual(uuid_bytes_old, parent_b.uuid_bytes)
    self.assertDictEqual({}, changes)

  def test_comparators(self):
    s = self.get_session()
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
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

  def test_json_encoder(self):
    s = self.get_session()
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    s.commit()

    parent = Parent()
    s.add(parent)
    s.commit()

    result = json.dumps(parent, cls=base.NummusJSONEncoder)
    target = json.dumps(parent.to_dict())
    self.assertEqual(target, result)

    today = datetime.date.today()
    d = {"class": ClassType.PARENT, "today": today}
    result = json.dumps(d, cls=base.NummusJSONEncoder)
    target = f'{{"class": "parent", "today": "{today.isoformat()}"}}'
    self.assertEqual(target, result)

    class Fake:
      """Unserializable class
      """
      pass

    d = {"obj": Fake()}
    self.assertRaises(TypeError, json.dumps, d, cls=base.NummusJSONEncoder)


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
