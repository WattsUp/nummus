from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.models import Label, LabelLink, query_count

if TYPE_CHECKING:

    from sqlalchemy import orm

    from nummus.models import Transaction


def test_init_properties(
    session: orm.Session,
    labels: dict[str, int],
    transactions: list[Transaction],
) -> None:
    d = {
        "label_id": labels["engineer"],
        "t_split_id": transactions[-1].splits[0].id_,
    }

    link = LabelLink(**d)
    session.add(link)
    session.commit()

    assert link.label_id == d["label_id"]
    assert link.t_split_id == d["t_split_id"]


def test_add_links_delete(
    session: orm.Session,
    transactions: list[Transaction],
    labels: dict[str, int],
) -> None:
    new_labels: dict[int, set[str]] = {txn.splits[0].id_: set() for txn in transactions}

    LabelLink.add_links(session, new_labels)

    n = query_count(session.query(LabelLink))
    assert n == 0

    n = query_count(session.query(Label))
    assert n == len(labels)


def test_add_links(
    session: orm.Session,
    transactions: list[Transaction],
    rand_str: str,
    labels: dict[str, int],
) -> None:
    new_labels: dict[int, set[str]] = {
        txn.splits[0].id_: {rand_str} for txn in transactions
    }

    LabelLink.add_links(session, new_labels)

    n = query_count(session.query(LabelLink))
    assert n == len(transactions)

    n = query_count(session.query(Label))
    assert n == len(labels) + 1

    label = session.query(Label).where(Label.id_.not_in(labels.values())).one()
    assert label.name == rand_str
