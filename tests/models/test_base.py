"""Test module nummus.models.base
"""

from __future__ import annotations
from typing import Dict, List, Optional

import datetime
import json
import uuid

import sqlalchemy
from sqlalchemy import orm

from nummus import models
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

  _hidden_column: orm.Mapped[Optional[int]]
  generic_column: orm.Mapped[Optional[int]]
  children: orm.Mapped[List[Child]] = orm.relationship(back_populates="parent")

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
    return self.uuid.encode(encoding="utf-8")


class ParentHidden(base.Base):
  """Test Parent class for Base.to_dict, Base.from_dict with hidden properties
  """

  _PROPERTIES_HIDDEN = ["generic_column"]

  _hidden_column: orm.Mapped[Optional[int]]
  generic_column: orm.Mapped[Optional[int]]
  _children: orm.Mapped[List[Child]] = orm.relationship(
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

  _hidden_column: orm.Mapped[Optional[int]]
  parent_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("parent.id"))
  parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")
  parent_hidden_id: orm.Mapped[Optional[int]] = orm.mapped_column(
      sqlalchemy.ForeignKey("parent_hidden.id"))
  parent_hidden: orm.Mapped[ParentHidden] = orm.relationship(
      back_populates="_children")

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
    session = self.get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent = Parent()
    self.assertIsNone(parent.id)
    self.assertIsNone(parent.uuid)
    session.add(parent)
    session.commit()
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
    session.add(child)
    session.commit()
    self.assertIsNotNone(child.id)
    self.assertIsNotNone(child.uuid)
    self.assertIsNotNone(child.parent)
    self.assertIsNotNone(child.parent_id)
    self.assertIsNone(child.parent_hidden)
    self.assertIsNone(child.parent_hidden_id)

  def test_to_dict(self):
    session = self.get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent = Parent()
    parent_hidden = ParentHidden()
    session.add_all([parent, parent_hidden])
    session.commit()

    child = Child(parent_id=parent.id)
    child.not_a_class_property = None
    session.add(child)
    session.commit()

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
    session.commit()

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
    session = self.get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent_a = Parent()
    parent_b = Parent()
    session.add_all([parent_a, parent_b])
    session.commit()

    d = {
        "id": int(self._RNG.integers(10, 1000)),
        "uuid": str(uuid.uuid4()),
        "age": int(self._RNG.integers(50, 100))
    }

    child_a = Child(parent=parent_a)
    child_b = Child(parent=parent_b)
    session.add_all([child_a, child_b])
    session.commit()

    self.assertEqual(1, len(parent_a.children))
    self.assertEqual(1, len(parent_b.children))

    id_old = child_a.id
    uuid_old = child_a.uuid
    age_old = child_a.age
    changes = child_a.update(d, force=False)
    session.commit()
    self.assertEqual(id_old, child_a.id)  # id is readonly
    self.assertEqual(uuid_old, child_a.uuid)  # uuid is readonly
    self.assertEqual(d["age"], child_a.age)
    self.assertDictEqual({"age": (age_old, d["age"])}, changes)

    # age is the same, not updated
    changes = child_a.update(d, force=True)
    session.commit()
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
    session.commit()
    self.assertEqual(d["age"], child_a.age)
    self.assertEqual(d["id"], child_a.id)
    self.assertEqual(d["uuid"], child_a.uuid)
    self.assertDictEqual({}, changes)

    # Update parent via id
    d = {"parent_id": parent_b.id}
    changes = child_a.update(d)
    session.commit()
    self.assertEqual(parent_b, child_a.parent)
    self.assertDictEqual({"parent_id": (parent_a.id, parent_b.id)}, changes)

    self.assertEqual(0, len(parent_a.children))
    self.assertEqual(2, len(parent_b.children))

    # Can't update relationships by obj
    d = {"parent": parent_a}
    changes = child_a.update(d)
    session.commit()
    self.assertEqual(parent_b, child_a.parent)
    self.assertEqual(parent_b.id, child_a.parent_id)
    self.assertDictEqual({}, changes)

    self.assertEqual(0, len(parent_a.children))
    self.assertEqual(2, len(parent_b.children))

    d = {"children": []}
    changes = parent_a.update(d)
    session.commit()
    self.assertEqual(parent_b, child_a.parent)
    self.assertDictEqual({}, changes)

    self.assertEqual(0, len(parent_a.children))
    self.assertEqual(2, len(parent_b.children))

    # Changing IDs is forcible but will cause IntegrityErrors upon execution
    id_old = parent_b.id
    d = {"id": str(uuid.uuid4())}
    changes = parent_b.update(d, force=True)
    self.assertRaises(models.exc.IntegrityError, session.commit)
    session.rollback()

    # Revert
    d = {"id": id_old}
    _ = parent_b.update(d, force=True)
    session.commit()
    self.assertEqual(id_old, parent_b.id)
    self.assertEqual(id_old, child_a.parent_id)
    self.assertEqual(parent_b, child_a.parent)

    d = {"id": id_old}

    # Hidden property will not update
    age_old = parent_b.age
    d = {"age": self._RNG.integers(50, 100)}
    changes = parent_b.update(d)
    session.commit()
    self.assertEqual(age_old, parent_b.age)
    self.assertDictEqual({}, changes)

    changes = parent_b.update(d, force=True)
    session.commit()
    self.assertEqual(d["age"], parent_b.age)
    self.assertDictEqual({"age": (age_old, d["age"])}, changes)

    # Property without a setter will not update
    uuid_bytes_old = parent_b.uuid_bytes
    d = {"uuid_bytes": str(uuid.uuid4()).encode()}
    changes = parent_b.update(d)
    session.commit()
    self.assertEqual(uuid_bytes_old, parent_b.uuid_bytes)
    self.assertDictEqual({}, changes)

  def test_comparators(self):
    session = self.get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent_a = Parent()
    parent_b = Parent()
    session.add_all([parent_a, parent_b])
    session.commit()

    self.assertEqual(parent_a, parent_a)
    self.assertNotEqual(parent_a, parent_b)

    # Make a new session to same DB
    with orm.create_session(bind=session.get_bind()) as session_2:
      # Get same parent_a but in a different Python object
      parent_a_queried = session_2.query(Parent).where(
          Parent.id == parent_a.id).first()
      self.assertNotEqual(id(parent_a), id(parent_a_queried))
      self.assertEqual(parent_a, parent_a_queried)

  def test_json_encoder(self):
    session = self.get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent = Parent()
    session.add(parent)
    session.commit()

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
  def _lut(cls) -> Dict[str, Derived]:
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
