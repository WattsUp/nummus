"""Derived exceptions for nummus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import DatabaseError, UnboundExecutionError

if TYPE_CHECKING:
    import datetime

    from nummus import custom_types as t

__all__ = [
    "DatabaseError",
    "UnboundExecutionError",
    "FileAlreadyImportedError",
    "UnknownImporterError",
    "UnlockingError",
    "NotEncryptedError",
]
# TODO (WattsUp): Add more custom exceptions when appropriate


class FileAlreadyImportedError(ValueError):
    """Error when a file has already been imported."""

    def __init__(self, date: datetime.date, path: t.Path) -> None:
        """Initialize FileAlreadyImportedError.

        Args:
            date: Date on which file was already imported
            path: Path to duplicate file
        """
        msg = f"Already imported {path} on {date}"
        super().__init__(msg)


class UnknownImporterError(ValueError):
    """Error when a file does not match any importer."""

    def __init__(self, path: t.Path) -> None:
        """Initialize UnknownImporterError.

        Args:
            path: Path to unknown file
        """
        msg = f"Unknown importer for {path}"
        super().__init__(msg)


class UnlockingError(PermissionError):
    """Error when portfolio fails to unlock."""


class NotEncryptedError(PermissionError):
    """Error when encryption operation is called on a unencrypted portfolio."""

    def __init__(self) -> None:
        """Initialize NotEncryptedError."""
        msg = "Portfolio is not encrypted"
        super().__init__(msg)


class ParentAttributeError(PermissionError):
    """Error when attempting to set an attribute directly instead of via parent."""


class NonAssetTransactionError(TypeError):
    """Error when attempting to perform Asset operation when Transaction has none."""

    def __init__(self) -> None:
        """Initialize NonAssetTransactionError."""
        msg = "Cannot perform operation on Transaction without an Asset"
        super().__init__(msg)
