"""TUI for portfolio."""

from __future__ import annotations

import colorama

from nummus.commands.backup_ import backup, restore
from nummus.commands.clean_ import clean
from nummus.commands.create_ import create
from nummus.commands.export_ import export
from nummus.commands.health_check_ import health_check
from nummus.commands.import_files_ import import_files
from nummus.commands.summarize_ import summarize
from nummus.commands.unlock_ import unlock
from nummus.commands.update_assets_ import update_assets
from nummus.commands.web_ import web

colorama.init(autoreset=True)


__all__ = [
    "backup",
    "restore",
    "clean",
    "create",
    "export",
    "health_check",
    "import_files",
    "summarize",
    "unlock",
    "update_assets",
    "web",
]
