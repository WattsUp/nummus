"""Base importer interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from nummus import custom_types as t

if TYPE_CHECKING:
    from pathlib import Path

TxnDict = dict[str, str | t.Real | t.Date | t.Any]
TxnDicts = list[TxnDict]


class TransactionImporter(ABC):
    """Importer that imports transactions."""

    def __init__(
        self,
        path: Path | None = None,
        buf: bytes | None = None,
    ) -> None:
        """Initialize Transaction Importer.

        Args:
            Provide one or the other
            path: Path to file
            buf: Contents of file
        """
        super().__init__()

        if buf is not None:
            self._buf = buf
        elif path is not None:
            with path.open("rb") as file:
                self._buf = file.read()
        else:
            msg = "Must provide path or buffer"
            raise ValueError(msg)

    @classmethod
    @abstractmethod
    def is_importable(cls, name: Path, buf: bytes) -> bool:
        """Test if file is importable for this Importer.

        Args:
            name: Name of file to import
            buf: Contents of file

        Returns:
            True if file is importable
        """

    @abstractmethod
    def run(self) -> TxnDicts:
        """Run importer.

        Returns:
            List of transaction as dictionaries, key mapping to Transaction
            properties. Accounts, Assets, and TransactionCategories referred to by
            name since ID is unknown here.
        """
