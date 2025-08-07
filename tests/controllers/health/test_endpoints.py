from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from nummus import health_checks

if TYPE_CHECKING:
    from sqlalchemy import orm

    from tests.controllers.conftest import WebClient


def test_page(web_client: WebClient) -> None:
    result, _ = web_client.GET("health.page")
    assert "Health checks" in result
    assert "Refresh" in result
    assert "Database integrity" in result
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
    assert "Database integrity" in result
    assert "warnings" in result
    assert "Last checks ran 0.0 seconds ago" in result


def test_ignore(web_client: WebClient, session: orm.Session) -> None:
    c = health_checks.UnusedCategories()
    c.test(session)
    session.commit()

    uri = next(iter(c.issues.keys()))

    result, _ = web_client.PUT(("health.ignore", {"uri": uri}))
    assert uri not in result
