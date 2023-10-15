"""Base importer interfaces."""

from abc import ABC, abstractmethod

from nummus import custom_types as t

TxnDict = t.Dict[str, t.Union[str, t.Real, t.Date, t.Any]]
TxnDicts = t.List[TxnDict]


class TransactionImporter(ABC):
    """Importer that imports transactions."""

    def __init__(
        self, path: t.Optional[str] = None, buf: t.Optional[bytes] = None
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
            with open(path, "rb") as file:
                self._buf = file.read()
        else:
            raise ValueError("Must provide path or buffer")

    @classmethod
    @abstractmethod
    def is_importable(cls, name: str, buf: bytes) -> bool:
        """Test if file is importable for this Importer.

        Args:
            name: Name of file to import
            buf: Contents of file

        Returns:
            True if file is importable
        """
        pass  # pragma: no cover

    @abstractmethod
    def run(self) -> TxnDicts:
        """Run importer.

        Returns:
            List of transaction as dictionaries, key mapping to Transaction
            properties. Accounts, Assets, and TransactionCategories referred to by
            name since ID is unknown here.
        """
        pass  # pragma: no cover
