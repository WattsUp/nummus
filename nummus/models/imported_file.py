"""Imported file model storing a hash and date of import."""

from __future__ import annotations

import datetime

from sqlalchemy import orm

from nummus import custom_types as t
from nummus.models.base import Base


class ImportedFile(Base):
    """Imported file model storing a hash and date of import.

    Attributes:
        hash_: SHA256 digest string of file contents
        date: Date of import
    """

    # No __table_id__ because this is not user accessible

    hash_: t.ORMStr = orm.MappedColumn(unique=True)
    date: t.ORMDate = orm.MappedColumn(default=datetime.date.today)
