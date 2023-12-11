from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, orm

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus.models import base
from tests.base import TestBase


class Bytes:
    def __init__(self, s: str) -> None:
        self._data = s.encode(encoding="utf-8")

    def __eq__(self, other: Bytes | t.Any) -> bool:
        return isinstance(other, Bytes) and self._data == other._data


class Parent(base.Base):
    __table_id__ = 0xF0000000

    generic_column: t.ORMIntOpt
    name: t.ORMStrOpt
    children: orm.Mapped[list[Child]] = orm.relationship(back_populates="parent")

    @property
    def favorite_child(self) -> Child | None:
        if len(self.children) < 1:
            return None
        return self.children[0]

    @property
    def uri_bytes(self) -> Bytes:
        return Bytes(self.uri)


class Child(base.Base):
    __table_id__ = 0xE0000000

    parent_id: t.ORMInt = orm.mapped_column(ForeignKey("parent.id_"))
    parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")

    height: t.ORMRealOpt = orm.mapped_column(base.Decimal6)


class TestORMBase(TestBase):
    def test_init_properties(self) -> None:
        s = self.get_session()
        base.Base.metadata.create_all(
            s.get_bind(),
            tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
        )
        s.commit()

        parent = Parent()
        self.assertIsNone(parent.id_)
        s.add(parent)
        s.commit()
        self.assertIsNotNone(parent.id_)
        self.assertIsNotNone(parent.uri)
        self.assertEqual(Parent.uri_to_id(parent.uri), parent.id_)

        child = Child()
        self.assertIsNone(child.id_)
        self.assertIsNone(child.parent)
        self.assertIsNone(child.parent_id)
        child.parent = parent
        s.add(child)
        s.commit()
        self.assertIsNotNone(child.id_)
        self.assertIsNotNone(child.uri)
        self.assertIsNotNone(child.parent)
        self.assertIsNotNone(child.parent_id)

        self.assertRaises(exc.WrongURITypeError, Parent.uri_to_id, child.uri)

        child.height = None
        s.commit()
        self.assertIsNone(child.height)

        height = Decimal("1.2")
        child.height = height
        s.commit()
        self.assertIsInstance(child.height, Decimal)
        self.assertEqual(child.height, height)

        # Only 6 decimals
        height = Decimal("1.23456789")
        child.height = height
        s.commit()
        self.assertIsInstance(child.height, Decimal)
        self.assertEqual(child.height, Decimal("1.234567"))

    def test_comparators(self) -> None:
        s = self.get_session()
        base.Base.metadata.create_all(
            s.get_bind(),
            tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
        )
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
            parent_a_queried = (
                session_2.query(Parent).where(Parent.id_ == parent_a.id_).first()
            )
            self.assertNotEqual(id(parent_a), id(parent_a_queried))
            self.assertEqual(parent_a, parent_a_queried)

    def test_map_name(self) -> None:
        s = self.get_session()
        base.Base.metadata.create_all(
            s.get_bind(),
            tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
        )
        s.commit()

        self.assertRaises(KeyError, base.Base.map_name, s)

        parent_a = Parent(name=self.random_string())
        parent_b = Parent(name=self.random_string())
        s.add_all([parent_a, parent_b])
        s.commit()

        result = Parent.map_name(s)
        target = {
            parent_a.id_: parent_a.name,
            parent_b.id_: parent_b.name,
        }
        self.assertEqual(result, target)

    def test_validate_strings(self) -> None:
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
        self.assertEqual(result, field)

        self.assertRaises(exc.InvalidORMValueError, parent.validate_strings, key, "ab")


class Derived(base.BaseEnum):
    RED = 1
    BLUE = 2

    @classmethod
    def _lut(cls) -> t.Mapping[str, Derived]:
        return {"r": cls.RED, "b": cls.BLUE}


class TestBaseEnum(TestBase):
    def test_missing(self) -> None:
        self.assertRaises(ValueError, Derived, None)
        self.assertRaises(ValueError, Derived, "")
        self.assertRaises(ValueError, Derived, "FAKE")

        for e in Derived:
            self.assertEqual(Derived(e), e)
            self.assertEqual(Derived(e.name), e)
            self.assertEqual(Derived(e.value), e)

        for s, e in Derived._lut().items():  # noqa: SLF001
            self.assertEqual(Derived(s.upper()), e)
