from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus.controllers import base
from nummus.models import (
    query_count,
    Tag,
    TagLink,
)

if TYPE_CHECKING:
    from sqlalchemy import orm

    from nummus.models import (
        Transaction,
    )
    from tests.controllers.conftest import WebClient


@pytest.mark.parametrize(
    ("s", "target"),
    [
        (" ", "Required"),
        ("i", "2 characters required"),
        ("new tag", ""),
    ],
)
def test_validation(
    web_client: WebClient,
    tags: dict[str, int],
    s: str,
    target: str,
) -> None:
    uri = Tag.id_to_uri(tags["engineer"])
    result, _ = web_client.GET(
        ("tags.validation", {"uri": uri, "name": s}),
    )
    assert result == target


def test_page(web_client: WebClient, tags: dict[str, int]) -> None:
    result, _ = web_client.GET("tags.page")
    for tag in tags:
        assert f"#{tag}" in result


def test_tag_get(web_client: WebClient, tags: dict[str, int]) -> None:
    uri = Tag.id_to_uri(tags["engineer"])
    result, _ = web_client.GET(("tags.tag", {"uri": uri}))
    assert "Edit tag" in result
    assert "engineer" in result
    assert "Delete" in result


def test_tag_delete(
    web_client: WebClient,
    tags: dict[str, int],
    session: orm.Session,
    transactions: list[Transaction],
) -> None:
    _ = transactions
    uri = Tag.id_to_uri(tags["engineer"])

    result, headers = web_client.DELETE(
        ("tags.tag", {"uri": uri}),
    )
    assert "snackbar.show" in result
    assert "Deleted tag engineer" in result
    assert headers["HX-Trigger"] == "tag"

    n = query_count(session.query(TagLink))
    assert n == 0


def test_tag_edit(
    web_client: WebClient,
    tags: dict[str, int],
    session: orm.Session,
) -> None:
    uri = Tag.id_to_uri(tags["engineer"])

    result, headers = web_client.PUT(
        ("tags.tag", {"uri": uri}),
        data={"name": "new tag"},
    )
    assert "snackbar.show" in result
    assert "All changes saved" in result
    assert headers["HX-Trigger"] == "tag"

    tag = session.query(Tag).where(Tag.name == "new tag").one()
    assert tag.id_ == tags["engineer"]


def test_tag_edit_error(
    web_client: WebClient,
    tags: dict[str, int],
) -> None:
    uri = Tag.id_to_uri(tags["engineer"])

    result, _ = web_client.PUT(
        ("tags.tag", {"uri": uri}),
        data={"name": "a"},
    )
    assert result == base.error("Tag name must be at least 2 characters long")
