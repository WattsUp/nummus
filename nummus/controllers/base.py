"""Base web controller functions."""

from __future__ import annotations

from collections.abc import Callable

Routes = dict[str, tuple[Callable, list[str]]]

__all__ = [
    "Routes",
]
