"""Financial source importers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.importers.base import TransactionImporter, TxnDict, TxnDicts
from nummus.importers.raw_csv import CSVTransactionImporter

if TYPE_CHECKING:
    from pathlib import Path

__all__ = [
    "TransactionImporter",
    "TxnDict",
    "TxnDicts",
    "get_importer",
]


def get_importer(path: Path) -> TransactionImporter | None:
    """Get the best importer for a file.

    Args:
        path: Path to file

    Returns:
        Initialized Importer
    """
    with path.open("rb") as file:
        buf = file.read()

    available = [CSVTransactionImporter]

    for i in available:
        if i.is_importable(path, buf):
            return i(buf=buf)
    return None
