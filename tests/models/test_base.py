"""Test module nummus.models.base
"""

from __future__ import annotations
from typing import List, Optional

import uuid

import sqlalchemy
from sqlalchemy import orm

from nummus import models
from nummus.models import base

from tests import base as test_base


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
  def id_bytes(self) -> bytes:
    """Get ID as bytes
    """
    return self.id.encode(encoding="utf-8")


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

  _PROPERTIES_DEFAULT = ["id", "age"]

  _hidden_column: orm.Mapped[Optional[int]]
  parent_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(36), sqlalchemy.ForeignKey("parent.id"))
  parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")
  parent_hidden_id: orm.Mapped[Optional[str]] = orm.mapped_column(
      sqlalchemy.String(36), sqlalchemy.ForeignKey("parent_hidden.id"))
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


class TestBase(test_base.TestBase):
  """Test ORM Base
  """

  def test_init_properties(self):
    session = self._get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent = Parent()
    self.assertIsNone(parent.id)
    session.add(parent)
    session.commit()
    self.assertIsNotNone(parent.id)

    child = Child()
    self.assertIsNone(child.id)
    self.assertIsNone(child.parent)
    self.assertIsNone(child.parent_id)
    self.assertIsNone(child.parent_hidden)
    self.assertIsNone(child.parent_hidden_id)
    child.parent = parent
    session.add(child)
    session.commit()
    self.assertIsNotNone(child.id)
    self.assertIsNotNone(child.parent)
    self.assertIsNotNone(child.parent_id)
    self.assertIsNone(child.parent_hidden)
    self.assertIsNone(child.parent_hidden_id)

  def test_to_dict(self):
    session = self._get_session()
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

    target = {"id": child.id, "age": child.age}
    d = child.to_dict()
    self.assertDictEqual(target, d)
    self.assertEqual(str(target), str(child))
    d = child.to_dict(hide=[""])  # Empty string ignored
    self.assertDictEqual(target, d)
    self.assertEqual(str(target), str(child))

    # Hide is stronger
    target = {"age": child.age, "parent_hidden": None}
    d = child.to_dict(hide=["id"], show=["id", "parent_hidden"])
    self.assertDictEqual(target, d)

    # Hide id but child is at Parent.Child
    target = {"id": child.id, "age": child.age}
    d = child.to_dict(hide=["id"],
                      path=f"{Parent.__tablename__}.{Child.__tablename__}")
    self.assertDictEqual(target, d)

    # Hide id in other ways
    target = {"age": child.age}
    d = child.to_dict(hide=[f"{Child.__tablename__}.id"])
    self.assertDictEqual(target, d)

    target = {"age": child.age}
    d = child.to_dict(hide=[".id"])
    self.assertDictEqual(target, d)

    # Test default Parent
    target = {"id": parent.id}
    d = parent.to_dict()
    self.assertDictEqual(target, d)

    target = {"id": parent_hidden.id}
    d = parent_hidden.to_dict()
    self.assertDictEqual(target, d)

    # Add a non-default property
    child.parent_hidden = parent_hidden
    session.commit()

    target = {
        "id": child.id,
        "parent_id": parent.id,
        "parent": {
            "id": parent.id
        },
        "parent_hidden": {
            "id": parent_hidden.id
        }
    }
    d = child.to_dict(show=["parent", "parent_id", "parent_hidden"],
                      hide=["age"])
    self.assertDictEqual(target, d)

    # Test non-serializable objects
    self.assertRaises(TypeError, parent.to_dict, show=["id_bytes"])

    # Test recursion and non-serializable objects
    target = {
        "id": parent.id,
        "children": [{
            "id": child.id,
            "age": child.age
        }],
        "favorite_child": {
            "id": child.id,
            "age": child.age
        }
    }
    d = parent.to_dict(show=["children", "favorite_child"])
    self.assertDictEqual(target, d)

    # Test recursion show/hiding
    target = {
        "id": parent.id,
        "age": parent.age,
        "children": [{
            "id": child.id
        }]
    }
    d = parent.to_dict(show=["children", "age"], hide=["children.age"])
    self.assertDictEqual(target, d)

    # Hide a relationship
    target = {"id": parent.id}
    d = parent.to_dict(hide=["children"])
    self.assertDictEqual(target, d)

    # Check hidden relationship is hidden
    target = {"id": parent_hidden.id}
    d = parent_hidden.to_dict()
    self.assertDictEqual(target, d)

    # Check hidden relationship is not shown when asked
    target = {"id": parent_hidden.id}
    d = parent_hidden.to_dict(show=["_children"])
    self.assertDictEqual(target, d)

  def test_update(self):
    session = self._get_session()
    base.Base.metadata.create_all(
        session.get_bind(),
        tables=[Parent.__table__, Child.__table__, ParentHidden.__table__])
    session.commit()

    parent_a = Parent()
    parent_b = Parent()
    session.add_all([parent_a, parent_b])
    session.commit()

    d = {"id": str(uuid.uuid4()), "age": self._RNG.integers(50, 100)}

    child_a = Child(parent=parent_a)
    child_b = Child(parent=parent_b)
    session.add_all([child_a, child_b])
    session.commit()

    self.assertEqual(1, len(parent_a.children))
    self.assertEqual(1, len(parent_b.children))

    id_old = child_a.id
    age_old = child_a.age
    changes = child_a.update(d, force=False)
    session.commit()
    self.assertEqual(id_old, child_a.id)  # id is readonly
    self.assertEqual(d["age"], child_a.age)
    self.assertDictEqual({"age": (age_old, d["age"])}, changes)

    # age is the same, not updated
    changes = child_a.update(d, force=True)
    session.commit()
    self.assertEqual(d["id"], child_a.id)
    self.assertEqual(d["age"], child_a.age)
    self.assertDictEqual({"id": (id_old, d["id"])}, changes)

    # Both are the same, not updated
    changes = child_a.update(d, force=True)
    session.commit()
    self.assertEqual(d["age"], child_a.age)
    self.assertEqual(d["id"], child_a.id)
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
    id_bytes_old = parent_b.id_bytes
    d = {"id_bytes": str(uuid.uuid4()).encode()}
    changes = parent_b.update(d)
    session.commit()
    self.assertEqual(id_bytes_old, parent_b.id_bytes)
    self.assertDictEqual({}, changes)
