from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.controllers import base
from nummus.controllers import labels as label_controller
from nummus.models import Label

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_ctx(session: orm.Session, labels: dict[str, int]) -> None:
    ctx = label_controller.ctx_labels(session)

    target: list[base.NamePair] = [
        base.NamePair(Label.id_to_uri(label_id), name)
        for name, label_id in sorted(labels.items())
    ]
    assert ctx == target
