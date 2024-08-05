"""Derived exceptions for nummus."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.exc import (
    DatabaseError,
    IntegrityError,
    MultipleResultsFound,
    NoResultFound,
    UnboundExecutionError,
)
from werkzeug import exceptions as http

if TYPE_CHECKING:
    import datetime
    from pathlib import Path


__all__ = [
    "DatabaseError",
    "IntegrityError",
    "MultipleResultsFound",
    "NoResultFound",
    "UnboundExecutionError",
    "http",
    "FileAlreadyImportedError",
    "UnknownImporterError",
    "EmptyImportError",
    "FailedImportError",
    "UnlockingError",
    "NotEncryptedError",
    "ParentAttributeError",
    "NonAssetTransactionError",
    "ProtectedObjectNotFoundError",
    "WrongURITypeError",
    "InvalidURIError",
    "InvalidORMValueError",
    "NoAssetWebSourceError",
    "AssetWebError",
    "UnknownEncryptionVersionError",
    "InvalidBackupTarError",
]


class FileAlreadyImportedError(Exception):
    """Error when a file has already been imported."""

    def __init__(self, date: datetime.date, path: Path) -> None:
        """Initialize FileAlreadyImportedError.

        Args:
            date: Date on which file was already imported
            path: Path to duplicate file
        """
        msg = f"Already imported {path} on {date}"
        super().__init__(msg)


class UnknownImporterError(Exception):
    """Error when a file does not match any importer."""

    def __init__(self, path: Path) -> None:
        """Initialize UnknownImporterError.

        Args:
            path: Path to unknown file
        """
        msg = f"Unknown importer for {path}"
        super().__init__(msg)


class EmptyImportError(Exception):
    """Error when a file does not return any transactions."""

    def __init__(self, path: Path, importer: object) -> None:
        """Initialize EmptyImportError.

        Args:
            path: Path to empty file
            importer: Importer used on file
        """
        msg = (
            f"No transactions imported for {path} using importer "
            f"{importer.__class__.__name__}"
        )
        super().__init__(msg)


class FailedImportError(Exception):
    """Error when a importer fails to import a file."""

    def __init__(self, path: Path, importer: object) -> None:
        """Initialize EmptyImportError.

        Args:
            path: Path to empty file
            importer: Importer used on file
        """
        msg = f"{importer.__class__.__name__} failed to import {path}"
        super().__init__(msg)


class UnlockingError(Exception):
    """Error when portfolio fails to unlock."""


class NotEncryptedError(Exception):
    """Error when encryption operation is called on a unencrypted portfolio."""

    def __init__(self) -> None:
        """Initialize NotEncryptedError."""
        msg = "Portfolio is not encrypted"
        super().__init__(msg)


class ParentAttributeError(Exception):
    """Error when attempting to set an attribute directly instead of via parent."""


class NonAssetTransactionError(Exception):
    """Error when attempting to perform Asset operation when Transaction has none."""

    def __init__(self) -> None:
        """Initialize NonAssetTransactionError."""
        msg = "Cannot perform operation on Transaction without an Asset"
        super().__init__(msg)


class ProtectedObjectNotFoundError(Exception):
    """Error when a protected object (non-deletable) could not be found."""


class WrongURITypeError(Exception):
    """Error when a URI is decoded for a different model."""


class InvalidURIError(Exception):
    """Error when object does not match expected URI format."""


class InvalidORMValueError(Exception):
    """Error when validation fails for an ORM column."""


class NoAssetWebSourceError(Exception):
    """Error when attempting to update AssetValutations when Asset has no web source."""

    def __init__(self) -> None:
        """Initialize NoAssetWebSourceError."""
        msg = "Cannot update AssetValutations without a web source, set ticker"
        super().__init__(msg)


class AssetWebError(Exception):
    """Error from a web source when attempting to update AssetValutations."""

    def __init__(self, e: Exception) -> None:
        """Initialize AssetWebError."""
        super().__init__(str(e))


class UnknownEncryptionVersionError(Exception):
    """Error when encryption config has an unknown version."""

    def __init__(self) -> None:
        """Initialize UnknownEncryptionVersionError."""
        msg = "Encryption config has an unrecognized version"
        super().__init__(msg)


class InvalidBackupTarError(Exception):
    """Error when a backup tar does not have expected contents."""
