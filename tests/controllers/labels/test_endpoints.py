from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import sql
from nummus.controllers import base
from nummus.models.label import Label, LabelLink

if TYPE_CHECKING:

    from nummus.models.transaction import Transaction
    from tests.controllers.conftest import WebClient


@pytest.mark.parametrize(
    ("s", "target"),
    [
        (" ", "Required"),
        ("i", "2 characters required"),
        ("new label", ""),
    ],
)
def test_validation(
    web_client: WebClient,
    labels: dict[str, int],
    s: str,
    target: str,
) -> None:
    uri = Label.id_to_uri(labels["engineer"])
    result, _ = web_client.GET(
        ("labels.validation", {"uri": uri, "name": s}),
    )
    assert result == target


def test_page(web_client: WebClient, labels: dict[str, int]) -> None:
    result, _ = web_client.GET("labels.page")
    for label in labels:
        assert label in result


def test_label_get(web_client: WebClient, labels: dict[str, int]) -> None:
    uri = Label.id_to_uri(labels["engineer"])
    result, _ = web_client.GET(("labels.label", {"uri": uri}))
    assert "Edit label" in result
    assert "engineer" in result
    assert "Delete" in result


def test_label_delete(
    web_client: WebClient,
    labels: dict[str, int],
    transactions: list[Transaction],
) -> None:
    uri = Label.id_to_uri(labels["engineer"])

    result, headers = web_client.DELETE(
        ("labels.label", {"uri": uri}),
    )
    assert "snackbar.show" in result
    assert "Deleted label engineer" in result
    assert "label" in headers["HX-Trigger"]

    assert not sql.any_(LabelLink.query())


def test_label_edit(
    web_client: WebClient,
    labels: dict[str, int],
) -> None:
    uri = Label.id_to_uri(labels["engineer"])

    result, headers = web_client.PUT(
        ("labels.label", {"uri": uri}),
        data={"name": "new label"},
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert "label" in headers["HX-Trigger"]

    label = sql.one(Label.query().where(Label.name == "new label"))
    assert label.id_ == labels["engineer"]


def test_label_edit_error(
    web_client: WebClient,
    labels: dict[str, int],
) -> None:
    uri = Label.id_to_uri(labels["engineer"])

    result, _ = web_client.PUT(
        ("labels.label", {"uri": uri}),
        data={"name": "a"},
    )
    assert result == base.error("Label name must be at least 2 characters long")
