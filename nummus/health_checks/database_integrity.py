"""Checks for issues in the underlying SQL database."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

import sqlalchemy

from nummus.health_checks.base import Base

if TYPE_CHECKING:
    from sqlalchemy import orm


class DatabaseIntegrity(Base):
    """Checks for issues in the underlying SQL database."""

    _DESC = "Checks for issues in the underlying SQL database."
    _SEVERE = True

    @override
    def test(self, s: orm.Session) -> None:
        result = s.execute(sqlalchemy.text("PRAGMA integrity_check"))
        rows = [row for row, in result.all()]
        if len(rows) != 1 or rows[0] != "ok":
            issues = {str(i): row for i, row in enumerate(rows)}
        else:
            issues = {}
        self._commit_issues(s, issues)
