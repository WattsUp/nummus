"""Test module nummus.models.base
"""

from __future__ import annotations
from typing import List

import sqlalchemy
from sqlalchemy import orm

from nummus.models import base

from tests import base as test_base


class Parent(base.Base):
  """Test Parent class for Base.to_dict, Base.from_dict
  """

  _PROPERTIES_HIDDEN = ["age"]

  _hidden_column: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer,
                                                      nullable=True)
  generic_column: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer,
                                                      nullable=True)
  children: orm.Mapped[List[Child]] = orm.relationship("Child",
                                                       back_populates="parent")

  _age = 40

  @property
  def age(self) -> int:
    """Age of parent in years
    """
    return self._age

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

  _hidden_column: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer,
                                                      nullable=True)
  generic_column: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer,
                                                      nullable=True)
  _children: orm.Mapped[List[Child]] = orm.relationship(
      "Child", back_populates="parent_hidden")

  _age = 43

  @property
  def age(self) -> int:
    """Age of parent in years
    """
    return self._age


class Child(base.Base):
  """Test Child class for Base.to_dict, Base.from_dict
  """

  _PROPERTIES_DEFAULT = ["id", "age"]

  _hidden_column: orm.Mapped[int] = orm.mapped_column(sqlalchemy.Integer,
                                                      nullable=True)
  parent_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(36), sqlalchemy.ForeignKey("parent.id"))
  parent: orm.Mapped[Parent] = orm.relationship("Parent",
                                                back_populates="children")
  parent_hidden_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(36),
      sqlalchemy.ForeignKey("parent_hidden.id"),
      nullable=True)
  parent_hidden: orm.Mapped[Parent] = orm.relationship(
      "ParentHidden", back_populates="_children")

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

    # Hide ID but child is at Parent.Child
    target = {"id": child.id, "age": child.age}
    d = child.to_dict(hide=["id"],
                      path=f"{Parent.__tablename__}.{Child.__tablename__}")
    self.assertDictEqual(target, d)

    # Hide ID in other ways
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
        "parent": {
            "id": parent.id
        },
        "parent_hidden": {
            "id": parent_hidden.id
        }
    }
    d = child.to_dict(show=["parent", "parent_hidden"], hide=["age"])
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
