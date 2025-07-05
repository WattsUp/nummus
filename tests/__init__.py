from __future__ import annotations

from pathlib import Path
from typing import TypedDict

TEST_LOG = Path("test_log.json").resolve()


class TestLog(TypedDict):
    classes: dict[str, float]
    methods: dict[str, float]
