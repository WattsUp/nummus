"""TUI for portfolio."""

from __future__ import annotations

from typing import TYPE_CHECKING

import colorama

from nummus.commands.backup import Backup, Restore
from nummus.commands.clean import Clean
from nummus.commands.create import Create
from nummus.commands.export import Export
from nummus.commands.health import Health
from nummus.commands.import_files import Import
from nummus.commands.summarize import Summarize
from nummus.commands.unlock import Unlock
from nummus.commands.update_assets import UpdateAssets
from nummus.commands.web import Web

if TYPE_CHECKING:
    from nummus.commands.base import Base


colorama.init(autoreset=True)


COMMANDS: dict[str, type[Base]] = {
    cls.NAME: cls
    for cls in [
        Create,
        Web,
        Unlock,
        Backup,
        Restore,
        Clean,
        Import,
        Export,
        UpdateAssets,
        Health,
        Summarize,
    ]
}
