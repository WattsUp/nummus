"""Imported file model storing a hash and date of import."""

from __future__ import annotations

import datetime

from sqlalchemy import orm

from nummus.models.base import Base, ORMInt, ORMStr, string_column_args


class ImportedFile(Base):
    """Imported file model storing a hash and date of import.

    Attributes:
        hash_: SHA256 digest string of file contents
        date: Date of import
    """

    # No __table_id__ because this is not user accessible

    hash_: ORMStr = orm.MappedColumn(unique=True)
    date_ord: ORMInt = orm.MappedColumn(
        default=lambda: datetime.date.today().toordinal(),
    )

    __table_args__ = (*string_column_args("hash_"),)

    @orm.validates("hash_")
    def validate_strings(self, key: str, field: str | None) -> str | None:
        """Validates string fields satisfy constraints."""
        return self.clean_strings(key, field, short_check=key != "ticker")
