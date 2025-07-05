from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import ForeignKey, orm

from nummus import exceptions as exc
from nummus import sql
from nummus.models import base

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from tests.conftest import RandomString


class Bytes:
    def __init__(self, s: str) -> None:
        self._data = s.encode(encoding="utf-8")

    def __eq__(self, other: Bytes | object) -> bool:
        return isinstance(other, Bytes) and self._data == other._data

    def __hash__(self) -> int:
        return hash(self._data)


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


def test_init_properties(tmp_path: Path) -> None:
    path = tmp_path / "sql.db"
    s = orm.Session(sql.get_engine(path, None))
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
    )
    s.commit()

    parent = Parent()
    assert parent.id_ is None
    with pytest.raises(exc.NoIDError):
        _ = parent.uri
    s.add(parent)
    s.commit()
    assert parent.id_ is not None
    assert parent.uri is not None
    assert Parent.uri_to_id(parent.uri) == parent.id_
    assert hash(parent) == parent.id_

    child = Child()
    assert child.id_ is None
    assert child.parent is None
    assert child.parent_id is None
    child.parent = parent
    s.add(child)
    s.commit()
    assert child.id_ is not None
    assert child.parent == parent
    assert child.parent_id == parent.id_

    with pytest.raises(exc.WrongURITypeError):
        Parent.uri_to_id(child.uri)

    child.height = None
    s.commit()
    assert child.height is None

    height = Decimal("1.2")
    child.height = height
    s.commit()
    assert isinstance(child.height, Decimal)
    assert child.height == height

    child.color = Derived.RED
    s.commit()
    assert isinstance(child.color, Derived)
    assert child.color == Derived.RED

    no_uri = NoURI(id_=1)
    with pytest.raises(exc.NoURIError):
        _ = no_uri.uri


def test_comparators(tmp_path: Path) -> None:
    path = tmp_path / "sql.db"
    s = orm.Session(sql.get_engine(path, None))
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
    )
    s.commit()

    parent_a = Parent()
    parent_b = Parent()
    s.add_all([parent_a, parent_b])
    s.commit()

    assert parent_a == parent_a  # noqa: PLR0124
    assert parent_a != parent_b

    # Make a new s to same DB
    with orm.create_session(bind=s.get_bind()) as session_2:
        # Get same parent_a but in a different Python object
        parent_a_queried = (
            session_2.query(Parent).where(Parent.id_ == parent_a.id_).first()
        )
        assert id(parent_a) != id(parent_a_queried)
        assert parent_a == parent_a_queried


def test_map_name(tmp_path: Path, rand_str: RandomString) -> None:
    path = tmp_path / "sql.db"
    s = orm.Session(sql.get_engine(path, None))
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
    )
    s.commit()

    with pytest.raises(KeyError, match="Base does not have name column"):
        base.Base.map_name(s)

    parent_a = Parent(name=rand_str())
    parent_b = Parent(name=rand_str())
    s.add_all([parent_a, parent_b])
    s.commit()

    target = {
        parent_a.id_: parent_a.name,
        parent_b.id_: parent_b.name,
    }
    assert Parent.map_name(s) == target


def test_clean_strings(tmp_path: Path, rand_str: RandomString) -> None:
    path = tmp_path / "sql.db"
    s = orm.Session(sql.get_engine(path, None))
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.__table__, Child.__table__],  # type: ignore[attr-defined]
    )
    s.commit()

    parent = Parent()
    s.add(parent)
    s.commit()

    parent.name = None
    assert parent.name is None

    parent.name = "    "
    assert parent.name is None

    field = rand_str(3)
    parent.name = field
    assert parent.name == field

    with pytest.raises(exc.InvalidORMValueError):
        parent.name = "a"

    # SQL errors when dirty strings get in
    s.query(Parent).update({Parent.name: None})
    s.commit()

    with pytest.raises(exc.IntegrityError):
        s.query(Parent).update({Parent.name: ""})
    s.rollback()

    with pytest.raises(exc.IntegrityError):
        s.query(Parent).update({Parent.name: " leading"})
    s.rollback()

    with pytest.raises(exc.IntegrityError):
        s.query(Parent).update({Parent.name: "trailing "})
    s.rollback()

    with pytest.raises(exc.IntegrityError):
        s.query(Parent).update({Parent.name: "a"})
    s.rollback()


def test_clean_decimals() -> None:
    child = Child()

    # Only 6 decimals
    height = Decimal("1.23456789")
    child.height = height
    assert child.height == Decimal("1.234567")


def test_clean_emoji_name(rand_str: RandomString) -> None:
    text = rand_str().lower()
    assert base.Base.clean_emoji_name(text.upper()) == text
    assert base.Base.clean_emoji_name(text + "😀 ") == text
