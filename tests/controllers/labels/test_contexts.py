from __future__ import annotations

from nummus.controllers import base
from nummus.controllers import labels as label_controller
from nummus.models.label import Label


def test_ctx(labels: dict[str, int]) -> None:
    ctx = label_controller.ctx_labels()

    target: list[base.NamePair] = [
        base.NamePair(Label.id_to_uri(label_id), name)
        for name, label_id in sorted(labels.items())
    ]
    assert ctx == target
