"""Base importer interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, TypedDict

from nummus import exceptions as exc

if TYPE_CHECKING:
    import datetime
    from decimal import Decimal


class TxnDict(TypedDict):
    """Type definition for imported transaction."""

    # Importers must import at least these items
    account: str
    date: datetime.date
    amount: Decimal
    statement: str | None

    # Importers may import these items
    payee: str | None
    memo: str | None
    category: str | None
    asset: str | None
    asset_quantity: Decimal | None


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

        Raises:
            NoImporterBufferError: If both bufs are None

        """
        super().__init__()

        self._buf = buf
        self._buf_pdf = buf_pdf

        if buf is None and buf_pdf is None:
            raise exc.NoImporterBufferError

    @classmethod
    @abstractmethod
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: list[str] | None,
    ) -> bool:
        """Test if file is importable for this Importer.

        Args:
            suffix: Suffix of file to import
            buf: Contents of file
            buf_pdf: Contents of PDF pages as text

        Returns:
            True if file is importable

        """
        raise NotImplementedError

    @abstractmethod
    def run(self) -> TxnDicts:
        """Run importer.

        Returns:
            List of transaction as dictionaries, key mapping to Transaction
            properties. Accounts, Assets, and TransactionCategories referred to by
            name since ID is unknown here.

        """
        raise NotImplementedError
