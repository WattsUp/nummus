from __future__ import annotations

from nummus import sql
from nummus.controllers import health
from nummus.health_checks.top import HEALTH_CHECKS
from nummus.models.transaction_category import TransactionCategory


def test_ctx_empty() -> None:
    ctx = health.ctx_checks(run=False)

    assert ctx["last_update_ago"] is None
    checks = ctx["checks"]
    assert len(checks) == len(HEALTH_CHECKS)
    has_issues = [c for c in checks if c["issues"]]
    assert not has_issues


def test_ctx_empty_run() -> None:
    ctx = health.ctx_checks(run=True)

    assert ctx["last_update_ago"] == 0
    checks = ctx["checks"]
    assert len(checks) == len(HEALTH_CHECKS)
    has_issues = [c for c in checks if c["issues"]]
    assert len(has_issues) == 1
    c = has_issues[0]
    assert c["name"] == "Unused categories"

    # All unused
    query = TransactionCategory.query().where(
        TransactionCategory.locked.is_(False),
    )
    assert len(c["issues"]) == sql.count(query)
