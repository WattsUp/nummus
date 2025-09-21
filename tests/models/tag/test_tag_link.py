from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models import query_count, Tag, TagLink

if TYPE_CHECKING:

    from sqlalchemy import orm

    from nummus.models import Transaction


def test_init_properties(
    session: orm.Session,
    tags: dict[str, int],
    transactions: list[Transaction],
) -> None:
    d = {
        "tag_id": tags["engineer"],
        "t_split_id": transactions[-1].splits[0].id_,
    }

    link = TagLink(**d)
    session.add(link)
    session.commit()

    assert link.tag_id == d["tag_id"]
    assert link.t_split_id == d["t_split_id"]


def test_add_links_delete(
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    tags: dict[int, set[str]] = {txn.splits[0].id_: set() for txn in transactions}

    TagLink.add_links(session, tags)

    n = query_count(session.query(TagLink))
    assert n == 0

    n = query_count(session.query(Tag))
    assert n == 0


def test_add_links(
    session: orm.Session,
    transactions: list[Transaction],
    rand_str: str,
) -> None:
    tags: dict[int, set[str]] = {txn.splits[0].id_: {rand_str} for txn in transactions}

    TagLink.add_links(session, tags)

    n = query_count(session.query(TagLink))
    assert n == len(transactions)

    n = query_count(session.query(Tag))
    assert n == 1

    tag = session.query(Tag).one()
    assert tag.name == rand_str
