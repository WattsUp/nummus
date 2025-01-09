from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, orm

from nummus import exceptions as exc
from nummus.models import base
from tests.base import TestBase

if TYPE_CHECKING:
    from collections.abc import Mapping


class Bytes:
    def __init__(self, s: str) -> None:
        self._data = s.encode(encoding="utf-8")

    def __eq__(self, other: Bytes | object) -> bool:
        return isinstance(other, Bytes) and self._data == other._data


class Derived(base.BaseEnum):
    RED = 1
    BLUE = 2
    SEAFOAM_GREEN = 3

    @classmethod
    def _lut(cls) -> Mapping[str, Derived]:
        return {"r": cls.RED, "b": cls.BLUE}


class Parent(base.Base):
    __table_id__ = 0xF0000000

    generic_column: base.ORMIntOpt
    name: base.ORMStrOpt
    children: orm.Mapped[list[Child]] = orm.relationship(back_populates="parent")

    __table_args__ = (*base.string_column_args("name"),)

    @orm.validates("name")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        return self.clean_strings(key, field)

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

    parent_id: base.ORMInt = orm.mapped_column(ForeignKey("parent.id_"))
    parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")

    height: base.ORMRealOpt = orm.mapped_column(base.Decimal6)

    color: orm.Mapped[Derived | None] = orm.mapped_column(base.SQLEnum(Derived))

    @orm.validates("height")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return self.clean_decimals(key, field)


class NoURI(base.Base):
    __table_id__ = None


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

        child.color = Derived.RED
        s.commit()
        self.assertIsInstance(child.color, Derived)
        self.assertEqual(child.color, Derived.RED)

        no_uri = NoURI()
        self.assertRaises(exc.NoURIError, getattr, no_uri, "uri")

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

    def test_clean_strings(self) -> None:
        s = self.get_session()
        base.Base.metadata.create_all(
            s.get_bind(),
            tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
        )
        s.commit()

        parent = Parent()
        s.add(parent)
        s.commit()

        parent.name = None
        self.assertIsNone(parent.name)

        parent.name = "    "
        self.assertIsNone(parent.name)

        parent.name = "[blank]"
        self.assertIsNone(parent.name)

        field = self.random_string(3)
        parent.name = field
        self.assertEqual(parent.name, field)

        self.assertRaises(exc.InvalidORMValueError, setattr, parent, "name", "a")

        # SQL errors when dirty strings get in
        s.query(Parent).update({Parent.name: None})
        s.commit()

        u = {Parent.name: ""}
        self.assertRaises(exc.IntegrityError, s.query(Parent).update, u)
        s.rollback()

        u = {Parent.name: "[blank]"}
        self.assertRaises(exc.IntegrityError, s.query(Parent).update, u)
        s.rollback()

        u = {Parent.name: " leading"}
        self.assertRaises(exc.IntegrityError, s.query(Parent).update, u)
        s.rollback()

        u = {Parent.name: "trailing "}
        self.assertRaises(exc.IntegrityError, s.query(Parent).update, u)
        s.rollback()

        u = {Parent.name: "a"}
        self.assertRaises(exc.IntegrityError, s.query(Parent).update, u)
        s.rollback()

    def test_clean_decimals(self) -> None:
        child = Child()

        # Only 6 decimals
        height = Decimal("1.23456789")
        child.height = height
        self.assertEqual(child.height, Decimal("1.234567"))


class TestBaseEnum(TestBase):
    def test_hasable(self) -> None:
        d = {
            Derived.RED: "red",
            Derived.BLUE: "blue",
        }
        self.assertIsInstance(d, dict)

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

    def test_comparators(self) -> None:
        self.assertEqual(Derived.RED, Derived.RED)
        self.assertEqual(Derived.RED, "RED")

        self.assertNotEqual(Derived.RED, Derived.BLUE)
        self.assertNotEqual(Derived.RED, "BLUE")

    def test_str(self) -> None:
        self.assertEqual(str(Derived.RED), "Derived.RED")
        self.assertEqual(str(Derived.SEAFOAM_GREEN), "Derived.SEAFOAM_GREEN")

    def test_pretty(self) -> None:
        self.assertEqual(Derived.RED.pretty, "Red")
        self.assertEqual(Derived.SEAFOAM_GREEN.pretty, "Seafoam Green")
