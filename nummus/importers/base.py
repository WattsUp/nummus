"""Base importer interfaces."""

from __future__ import annotations

import datetime
from abc import ABC, abstractmethod
from decimal import Decimal

TxnDict = dict[str, str | Decimal | datetime.date | object]
TxnDicts = list[TxnDict]


class TransactionImporter(ABC):
    """Importer that imports transactions."""

    def __init__(
        self,
        buf: bytes | None = None,
        buf_pdf: list[str] | None = None,
    ) -> None:
        """Initialize Transaction Importer.

        Args:
            Provide one or the other
            buf: Contents of file
            buf_pdf: Contents of PDF pages as text
        """
        super().__init__()

        self._buf = buf
        self._buf_pdf = buf_pdf

        if buf is None and buf_pdf is None:
            msg = "Must provide buffer or PDF pages"
            raise ValueError(msg)

    @classmethod
    @abstractmethod
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: list[str] | None,
    ) -> bool:  # pragma: no cover
        """Test if file is importable for this Importer.

        Args:
            suffix: Suffix of file to import
            buf: Contents of file
            buf_pdf: Contents of PDF pages as text

        Returns:
            True if file is importable
        """
        msg = f"Method not implemented for {cls}"
        raise NotImplementedError(msg)

    @abstractmethod
    def run(self) -> TxnDicts:  # pragma: no cover
        """Run importer.

        Returns:
            List of transaction as dictionaries, key mapping to Transaction
            properties. Accounts, Assets, and TransactionCategories referred to by
            name since ID is unknown here.
        """
        msg = f"Method not implemented for {self.__class__}"
        raise NotImplementedError(msg)
