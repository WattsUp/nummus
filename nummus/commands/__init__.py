"""TUI for portfolio."""

from __future__ import annotations

import colorama

from nummus.commands.backup import backup, restore
from nummus.commands.clean import clean
from nummus.commands.create import create
from nummus.commands.health_check import health_check
from nummus.commands.import_files import import_files
from nummus.commands.summarize import summarize
from nummus.commands.unlock import unlock
from nummus.commands.update_assets import update_assets
from nummus.commands.web import run_web

colorama.init(autoreset=True)


__all__ = [
    "backup",
    "restore",
    "clean",
    "create",
    "health_check",
    "import_files",
    "summarize",
    "unlock",
    "update_assets",
    "run_web",
]
