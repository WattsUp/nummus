from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import base
from nummus.controllers import tags as tag_controller
from nummus.models import Tag

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_ctx(session: orm.Session, tags: dict[str, int]) -> None:
    ctx = tag_controller.ctx_tags(session)

    target: list[base.NamePair] = [
        base.NamePair(Tag.id_to_uri(tag_id), name)
        for name, tag_id in sorted(tags.items())
    ]
    assert ctx == target
