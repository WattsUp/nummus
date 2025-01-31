"""Checks for issues in the underlying SQL database."""

from __future__ import annotations

import sqlalchemy
from typing_extensions import override

from nummus.health_checks.base import Base


class DatabaseIntegrity(Base):
    """Checks for issues in the underlying SQL database."""

    _DESC = "Checks for issues in the underlying SQL database."
    _SEVERE = True

    @override
    def test(self) -> None:
        with self._p.begin_session() as s:
            result = s.execute(sqlalchemy.text("PRAGMA integrity_check"))
            rows = [row for row, in result.all()]
            if len(rows) != 1 or rows[0] != "ok":
                self._issues_raw = {str(i): row for i, row in enumerate(rows)}

        self._commit_issues()
