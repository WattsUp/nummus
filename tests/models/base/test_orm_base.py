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

    from tests.conftest import RandomStringGenerator


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
    def lut(cls) -> Mapping[str, Derived]:
        return {"r": cls.RED, "b": cls.BLUE}


class Parent(base.Base):
    __tablename__ = "parent"
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
    __tablename__ = "child"
    __table_id__ = 0xE0000000

    parent_id: base.ORMInt = orm.mapped_column(ForeignKey("parent.id_"))
    parent: orm.Mapped[Parent] = orm.relationship(back_populates="children")

    height: base.ORMRealOpt = orm.mapped_column(base.Decimal6)

    color: orm.Mapped[Derived | None] = orm.mapped_column(base.SQLEnum(Derived))

    @orm.validates("height")
    def validate_decimals(self, key: str, field: Decimal | None) -> Decimal | None:
        return self.clean_decimals(key, field)


class NoURI(base.Base):
    __tablename__ = "no_uri"
    __table_id__ = None


@pytest.fixture
def session(tmp_path: Path) -> orm.Session:
    """Create SQL session.

    Args:
        tmp_path: Temp path to create DB in

    Returns:
        Session generator

    """
    path = tmp_path / "sql.db"
    s = orm.Session(sql.get_engine(path, None))
    base.Base.metadata.create_all(
        s.get_bind(),
        tables=[Parent.sql_table(), Child.sql_table()],
    )
    s.commit()
    return s


@pytest.fixture
def parent(session: orm.Session) -> Parent:
    """Create a Parent.

    Returns:
        Parent

    """
    p = Parent()
    session.add(p)
    session.commit()
    return p


@pytest.fixture
def child(session: orm.Session, parent: Parent) -> Child:
    """Create a Child.

    Returns:
        Child

    """
    c = Child(parent=parent)
    session.add(c)
    session.commit()
    return c


def test_detached() -> None:
    parent = Parent()
    assert parent.id_ is None
    with pytest.raises(exc.NoIDError):
        _ = parent.uri


def test_init_properties(parent: Parent) -> None:
    assert parent.id_ is not None
    assert parent.uri is not None
    assert Parent.uri_to_id(parent.uri) == parent.id_
    assert hash(parent) == parent.id_


def test_detached_child() -> None:
    child = Child()
    assert child.id_ is None
    assert child.parent is None
    assert child.parent_id is None


def test_link_child(parent: Parent, child: Child) -> None:
    assert child.id_ is not None
    assert child.parent == parent
    assert child.parent_id == parent.id_


def test_wrong_uri_type(parent: Parent) -> None:
    with pytest.raises(exc.WrongURITypeError):
        Child.uri_to_id(parent.uri)


def test_set_decimal_none(session: orm.Session, child: Child) -> None:
    child.height = None
    session.commit()
    assert child.height is None


def test_set_decimal_value(session: orm.Session, child: Child) -> None:
    height = Decimal("1.2")
    child.height = height
    session.commit()
    assert isinstance(child.height, Decimal)
    assert child.height == height


def test_set_enum(session: orm.Session, child: Child) -> None:
    child.color = Derived.RED
    session.commit()
    assert isinstance(child.color, Derived)
    assert child.color == Derived.RED


def test_no_uri() -> None:
    no_uri = NoURI(id_=1)
    with pytest.raises(exc.NoURIError):
        _ = no_uri.uri


def test_comparators_same_session(session: orm.Session) -> None:
    parent_a = Parent()
    parent_b = Parent()
    session.add_all([parent_a, parent_b])
    session.commit()

    assert parent_a == parent_a  # noqa: PLR0124
    assert parent_a != parent_b


def test_comparators_different_session(session: orm.Session, parent: Parent) -> None:
    # Make a new s to same DB
    with orm.create_session(bind=session.get_bind()) as session_2:
        # Get same parent_a but in a different Python object
        parent_a_queried = (
            session_2.query(Parent).where(Parent.id_ == parent.id_).first()
        )
        assert id(parent) != id(parent_a_queried)
        assert parent == parent_a_queried


def test_map_name_none(session: orm.Session) -> None:
    with pytest.raises(KeyError, match="Base does not have name column"):
        base.Base.map_name(session)


def test_map_name_parent(
    session: orm.Session,
    rand_str_generator: RandomStringGenerator,
) -> None:
    parent_a = Parent(name=rand_str_generator())
    parent_b = Parent(name=rand_str_generator())
    session.add_all([parent_a, parent_b])
    session.commit()

    target = {
        parent_a.id_: parent_a.name,
        parent_b.id_: parent_b.name,
    }
    assert Parent.map_name(session) == target


def test_clean_strings_none(parent: Parent) -> None:
    parent.name = None
    assert parent.name is None


def test_clean_strings_empty(parent: Parent) -> None:
    parent.name = "    "
    assert parent.name is None


def test_clean_strings_good(
    parent: Parent,
    rand_str_generator: RandomStringGenerator,
) -> None:
    field = rand_str_generator(3)
    parent.name = field
    assert parent.name == field


def test_clean_strings_short(parent: Parent) -> None:
    with pytest.raises(exc.InvalidORMValueError):
        parent.name = "a"


def test_string_check_none(session: orm.Session, parent: Parent) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(Parent).where(Parent.id_ == parent.id_).update({Parent.name: ""})


def test_string_check_leading(session: orm.Session, parent: Parent) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(Parent).where(Parent.id_ == parent.id_).update(
            {Parent.name: " leading"},
        )


def test_string_check_trailing(session: orm.Session, parent: Parent) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(Parent).where(Parent.id_ == parent.id_).update(
            {Parent.name: "trailing "},
        )


def test_string_check_short(session: orm.Session, parent: Parent) -> None:
    with pytest.raises(exc.IntegrityError):
        session.query(Parent).where(Parent.id_ == parent.id_).update({Parent.name: "a"})


def test_clean_decimals() -> None:
    child = Child()

    # Only 6 decimals
    height = Decimal("1.23456789")
    child.height = height
    assert child.height == Decimal("1.234567")


def test_clean_emoji_name(rand_str: str) -> None:
    text = rand_str.lower()
    assert base.Base.clean_emoji_name(text + " 😀 ") == text


def test_clean_emoji_name_upper(rand_str: str) -> None:
    text = rand_str.lower()
    assert base.Base.clean_emoji_name(text.upper() + " 😀 ") == text
