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
    "AssetWebError",
    "ComputedColumnError",
    "DatabaseError",
    "DuplicateURLError",
    "EmptyImportError",
    "EmptySearchError",
    "EvaluationError",
    "FailedImportError",
    "FileAlreadyImportedError",
    "FutureTransactionError",
    "IntegrityError",
    "InvalidAssetTransactionCategoryError",
    "InvalidBackupTarError",
    "InvalidKeyError",
    "InvalidORMValueError",
    "InvalidURIError",
    "MigrationRequiredError",
    "MissingAssetError",
    "MultipleResultsFound",
    "NoAssetWebSourceError",
    "NoIDError",
    "NoImporterBufferError",
    "NoResultFound",
    "NoURIError",
    "NonAssetTransactionError",
    "NotEncryptedError",
    "ParentAttributeError",
    "ProtectedObjectNotFoundError",
    "UnboundExecutionError",
    "UnknownEncryptionVersionError",
    "UnknownImporterError",
    "UnlockingError",
    "WrongImporterBufferError",
    "WrongURITypeError",
    "http",
]


class DuplicateURLError(Exception):
    """Error when a URL already exists with a endpoint."""

    def __init__(self, url: str, endpoint: str) -> None:  # pragma: no cover
        """Initialize DuplicateURLError.

        Args:
            url: Duplicate URL
            endpoint: Attempted endpoint

        """
        msg = f"Already have a route on {url}, cannot add {endpoint}"
        super().__init__(msg)


class FileAlreadyImportedError(Exception):
    """Error when a file has already been imported."""

    def __init__(self, date: datetime.date, path: Path) -> None:
        """Initialize FileAlreadyImportedError.

        Args:
            date: Date on which file was already imported
            path: Path to duplicate file

        """
        self.date = date
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
        self.importer = importer.__class__.__name__
        msg = (
            f"No transactions imported for {path} using importer "
            f"{importer.__class__.__name__}"
        )
        super().__init__(msg)


class FailedImportError(Exception):
    """Error when an importer fails to import a file."""

    def __init__(self, path: Path, importer: object) -> None:
        """Initialize FailedImportError.

        Args:
            path: Path to empty file
            importer: Importer used on file

        """
        self.importer = importer.__class__.__name__
        msg = f"{importer.__class__.__name__} failed to import {path}"
        super().__init__(msg)


class WrongImporterBufferError(Exception):
    """Error when an importer is run with the wrong buffer type."""


class NoImporterBufferError(Exception):
    """Error when an importer is run without a buffer."""


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


class NoIDError(Exception):
    """Error when model does not have id_ yet, likely a flush is needed."""


class NoURIError(Exception):
    """Error when a URI is requested for a model without one."""


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


class FutureTransactionError(Exception):
    """Error when attempting to create a Transaction in the future."""

    def __init__(self) -> None:
        """Initialize FutureTransactionError."""
        msg = "Cannot create Transaction in the future"
        super().__init__(msg)


class MissingAssetError(Exception):
    """Error when transaction is missing Asset information."""


class ComputedColumnError(Exception):
    """Error when attempting to set a computed column."""


class EvaluationError(Exception):
    """Error encountered when evaluating expression."""


class MigrationRequiredError(Exception):
    """Error when a migration is needed to operate."""


class EmptySearchError(Exception):
    """Error when search query has no tokens."""


class InvalidAssetTransactionCategoryError(Exception):
    """Error when a category for an asset transaction is invalid."""


class InvalidKeyError(Exception):
    """Error when a key does not meet minimum requirements."""
