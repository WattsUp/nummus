"""Checks for issues in the underlying SQL database."""

from __future__ import annotations

from typing import override, TYPE_CHECKING

import sqlalchemy

from nummus import sql
from nummus.health_checks.base import HealthCheck
from nummus.models.base import Base

if TYPE_CHECKING:
    from sqlalchemy import orm


class DatabaseIntegrity(HealthCheck):
    """Checks for issues in the underlying SQL database."""

    _DESC = "Checks for issues in the underlying SQL database."
    _SEVERE = True

    @override
    def test(self) -> None:
        query: orm.query.RowReturningQuery[tuple[str]] = Base.session().execute(  # type: ignore[attr-defined]
            sqlalchemy.text("PRAGMA integrity_check"),
        )
        rows = list(sql.col0(query))
        if len(rows) != 1 or rows[0] != "ok":
            issues = {str(i): row for i, row in enumerate(rows)}
        else:
            issues = {}
        self._commit_issues(issues)
