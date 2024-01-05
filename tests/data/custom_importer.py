"""Custom importer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nummus.importers import base

if TYPE_CHECKING:
    from nummus import custom_types as t


class BananaBankImporter(base.TransactionImporter):
    @classmethod
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: t.Strings | None,
    ) -> bool:
        _ = buf
        _ = buf_pdf
        return suffix == ".pdf"

    def run(self) -> base.TxnDicts:
        return []
