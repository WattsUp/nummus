"""Financial source importers."""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING

import pdfplumber

from nummus.importers.base import TransactionImporter, TxnDict, TxnDicts
from nummus.importers.raw_csv import CSVTransactionImporter

if TYPE_CHECKING:
    from pathlib import Path

    from nummus import custom_types as t

__all__ = [
    "TransactionImporter",
    "TxnDict",
    "TxnDicts",
    "get_importer",
]


def get_importers(extra: Path | None) -> t.Sequence[type[TransactionImporter]]:
    """Get a list of importers from a directory.

    Args:
        extra: Path to extra importers directory

    Return:
        List of base importers and any in extra directory
    """
    available = [
        CSVTransactionImporter,
    ]
    if extra is None:
        return tuple(available)
    for file in extra.glob("**/*.py"):
        name = ".".join(file.relative_to(extra).parts[:-1] + (file.name.split(".")[0],))
        spec = importlib.util.spec_from_file_location(name, file)
        if spec is None or spec.loader is None:  # pragma: no cover
            msg = f"Failed to create spec for {file}"
            raise ImportError(msg)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for key in dir(module):
            # Iterate module to find derived importers
            if key[0] == "_":
                continue
            obj = getattr(module, key)
            if (
                not isinstance(obj, type(TransactionImporter))
                or obj == TransactionImporter
            ):
                continue
            available.append(obj)

    return tuple(available)


def get_importer(
    path: Path,
    available: t.Sequence[type[TransactionImporter]],
) -> TransactionImporter | None:
    """Get the best importer for a file.

    Args:
        path: Path to file
        available: Available importers for portfolio

    Returns:
        Initialized Importer
    """
    suffix = path.suffix.lower()

    buf: bytes | None = None
    buf_pdf: t.Strings | None = None
    if suffix == ".pdf":
        buf_pdf = []
        with pdfplumber.open(path) as pdf:
            pages = [page.extract_text() for page in pdf.pages]
            buf_pdf = [page for page in pages if page]
    else:
        with path.open("rb") as file:
            buf = file.read()

    for i in available:
        if i.is_importable(suffix, buf=buf, buf_pdf=buf_pdf):
            return i(buf=buf, buf_pdf=buf_pdf)
    return None
