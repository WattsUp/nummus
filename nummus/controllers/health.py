"""Health controllers."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import health_checks, portfolio
from nummus.controllers import common
from nummus.models.base import YIELD_PER
from nummus.models.health_checks import HealthCheckIssue

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


class HealthCheckContext(TypedDict):
    """Type definition for health check context."""

    name: str
    description: str
    is_severe: bool
    issues: list[str]


def ctx_checks(*, run: bool) -> list[HealthCheckContext]:
    """Get the context to build the health checks.

    Args:
        run: True will rerun health checks

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    issues: dict[str, list[str]] = defaultdict(list)
    if not run:
        with p.begin_session() as s:
            query = s.query(HealthCheckIssue).where(HealthCheckIssue.ignore.is_(False))
            for i in query.yield_per(YIELD_PER):
                issues[i.check].append(i.msg)

    ctx: list[HealthCheckContext] = []
    for check_type in health_checks.CHECKS:
        c = check_type(p)

        if run:
            c.test()

        ctx.append(
            {
                "name": c.name,
                "description": c.description,
                "is_severe": c.is_severe,
                "issues": sorted(c.issues.values() if run else issues[c.name]),
            },
        )
    return ctx


def page() -> str:
    """GET /health.

    Returns:
        string HTML response
    """
    return common.page(
        "health/index-content.jinja",
        title="Health",
        checks=ctx_checks(run=False),
    )


def refresh() -> str:
    """POST /h/health/refresh.

    Returns:
        string HTML response
    """
    return flask.render_template(
        "health/checks.jinja",
        checks=ctx_checks(run=True),
    )


ROUTES: Routes = {
    "/health": (page, ["GET"]),
    "/h/health/refresh": (refresh, ["POST"]),
}
