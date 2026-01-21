from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import sql
from nummus.models.label import Label, LabelLink

if TYPE_CHECKING:
    from nummus.models.transaction import Transaction


def test_init_properties(
    labels: dict[str, int],
    transactions: list[Transaction],
) -> None:
    d = {
        "label_id": labels["engineer"],
        "t_split_id": transactions[-1].splits[0].id_,
    }

    link = LabelLink.create(**d)

    assert link.label_id == d["label_id"]
    assert link.t_split_id == d["t_split_id"]


def test_add_links_delete(
    transactions: list[Transaction],
    labels: dict[str, int],
) -> None:
    new_labels: dict[int, set[str]] = {txn.splits[0].id_: set() for txn in transactions}

    LabelLink.add_links(new_labels)

    assert not sql.any_(LabelLink.query())
    assert sql.count(Label.query()) == len(labels)


def test_add_links(
    transactions: list[Transaction],
    rand_str: str,
    labels: dict[str, int],
) -> None:
    new_labels: dict[int, set[str]] = {
        txn.splits[0].id_: {rand_str, "engineer"} for txn in transactions
    }

    LabelLink.add_links(new_labels)

    assert sql.count(LabelLink.query()) == len(transactions) * 2
    assert sql.count(Label.query()) == len(labels) + 1

    label = Label.query().where(Label.id_.not_in(labels.values())).one()
    assert label.name == rand_str
