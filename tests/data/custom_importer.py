"""Custom importer."""

from __future__ import annotations

from typing import override

from nummus.importers import base


class BananaBankImporter(base.TransactionImporter):
    @classmethod
    def is_importable(
        cls,
        suffix: str,
        buf: bytes | None,
        buf_pdf: list[str] | None,
    ) -> bool:
        _ = buf
        _ = buf_pdf
        return suffix == ".pdf"

    @override
    def run(self) -> base.TxnDicts:
        return []
