from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import health_checks
from nummus.controllers import health
from nummus.models import query_count, TransactionCategory

if TYPE_CHECKING:
    import flask
    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


def test_empty(flask_app: flask.Flask) -> None:
    with flask_app.app_context():
        ctx = health.ctx_checks(run=False)

    assert ctx["last_update_ago"] is None
    checks = ctx["checks"]
    assert len(checks) == len(health_checks.CHECKS)
    has_issues = [c for c in checks if c["issues"]]
    assert not has_issues


def test_empty_run(flask_app: flask.Flask, session: orm.Session) -> None:
    with flask_app.app_context():
        ctx = health.ctx_checks(run=True)

    assert ctx["last_update_ago"] == 0
    checks = ctx["checks"]
    assert len(checks) == len(health_checks.CHECKS)
    has_issues = [c for c in checks if c["issues"]]
    assert len(has_issues) == 1
    c = has_issues[0]
    assert c["name"] == "Unused Categories"

    # All unused
    query = session.query(TransactionCategory).where(
        TransactionCategory.locked.is_(False),
    )
    assert len(c["issues"]) == query_count(query)


def test_page(web_client: WebClient) -> None:
    result, _ = web_client.GET("health.page")
    assert "Health checks" in result
    assert "Refresh" in result
    assert "Database Integrity" in result
    assert "warnings" not in result
    assert "Health checks never ran" in result


# For creating new LAST_HEALTH_CHECK_TS or modifying it
@pytest.mark.parametrize("n_runs", [1, 2])
def test_refresh(web_client: WebClient, n_runs: int) -> None:
    for _ in range(n_runs - 1):
        web_client.POST("health.refresh")
    result, _ = web_client.POST("health.refresh")
    assert "Health checks" not in result
    assert "Refresh" not in result
    assert "Database Integrity" in result
    assert "warnings" in result
    assert "Last checks ran 0.0 seconds ago" in result


def test_ignore(web_client: WebClient, session: orm.Session) -> None:
    c = health_checks.UnusedCategories()
    c.test(session)
    session.commit()

    uri = next(iter(c.issues.keys()))

    result, _ = web_client.PUT(("health.ignore", {"uri": uri}))
    assert uri not in result
