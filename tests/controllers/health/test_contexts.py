from __future__ import annotations

from typing import TYPE_CHECKING

from nummus import health_checks
from nummus.controllers import health
from nummus.models import query_count, TransactionCategory

if TYPE_CHECKING:
    from sqlalchemy import orm


def test_ctx_empty(session: orm.Session) -> None:
    ctx = health.ctx_checks(session, run=False)

    assert ctx["last_update_ago"] is None
    checks = ctx["checks"]
    assert len(checks) == len(health_checks.CHECKS)
    has_issues = [c for c in checks if c["issues"]]
    assert not has_issues


def test_ctx_empty_run(session: orm.Session) -> None:
    ctx = health.ctx_checks(session, run=True)

    assert ctx["last_update_ago"] == 0
    checks = ctx["checks"]
    assert len(checks) == len(health_checks.CHECKS)
    has_issues = [c for c in checks if c["issues"]]
    assert len(has_issues) == 1
    c = has_issues[0]
    assert c["name"] == "Unused categories"

    # All unused
    query = session.query(TransactionCategory).where(
        TransactionCategory.locked.is_(False),
    )
    assert len(c["issues"]) == query_count(query)
