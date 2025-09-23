"""Health controllers."""

from __future__ import annotations

import datetime
import operator
from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import health_checks, web
from nummus.controllers import base
from nummus.models import Config, ConfigKey, HealthCheckIssue, YIELD_PER

if TYPE_CHECKING:
    from sqlalchemy import orm


class HealthContext(TypedDict):
    """Type definition for health page context."""

    last_update_ago: float | None
    checks: list[HealthCheckContext]


class HealthCheckContext(TypedDict):
    """Type definition for health check context."""

    name: str
    uri: str
    description: str
    is_severe: bool
    issues: dict[str, str]


def page() -> flask.Response:
    """GET /health.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        return base.page(
            "health/page.jinja",
            title="Health",
            ctx=ctx_checks(s, run=False),
        )


def refresh() -> str:
    """POST /h/health/refresh.

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        return flask.render_template(
            "health/checks.jinja",
            ctx=ctx_checks(s, run=True),
            include_oob=True,
        )


def ignore(uri: str) -> str:
    """PUT /h/health/i/<uri>/ignore.

    Args:
        uri: HealthCheckIssue uri to ignore

    Returns:
        string HTML response

    """
    p = web.portfolio
    with p.begin_session() as s:
        c = base.find(s, HealthCheckIssue, uri)
        c.ignore = True
        name = c.check

        checks = ctx_checks(s, run=False)["checks"]

    return flask.render_template(
        "health/check-row.jinja",
        check=next(c for c in checks if c["name"] == name),
        oob=True,
    )


def ctx_checks(s: orm.Session, *, run: bool) -> HealthContext:
    """Get the context to build the health checks.

    Args:
        s: SQL session to use
        run: True will rerun health checks

    Returns:
        Dictionary HTML context

    """
    utc_now = datetime.datetime.now(datetime.UTC)

    issues: dict[str, dict[str, str]] = defaultdict(dict)
    if run:
        c = (
            s.query(Config)
            .where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS)
            .one_or_none()
        )
        if c is None:
            c = Config(
                key=ConfigKey.LAST_HEALTH_CHECK_TS,
                value=utc_now.isoformat(),
            )
            s.add(c)
        else:
            c.value = utc_now.isoformat()
        last_update = utc_now
    else:
        last_update_str = (
            s.query(Config.value)
            .where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS)
            .scalar()
        )
        last_update = (
            None
            if last_update_str is None
            else datetime.datetime.fromisoformat(last_update_str)
        )
        query = s.query(HealthCheckIssue).where(HealthCheckIssue.ignore.is_(False))
        for i in query.yield_per(YIELD_PER):
            issues[i.check][i.uri] = i.msg

    checks: list[HealthCheckContext] = []
    for check_type in health_checks.CHECKS:
        name = check_type.name()

        if run:
            c = check_type()
            c.test(s)
            c_issues = c.issues
        else:
            c_issues = issues[name]

        checks.append(
            {
                "name": name,
                "uri": name.replace(" ", "-").lower(),
                "description": check_type.description(),
                "is_severe": check_type.is_severe(),
                "issues": dict(sorted(c_issues.items(), key=operator.itemgetter(1))),
            },
        )
    return {
        "checks": checks,
        "last_update_ago": (
            None if last_update is None else (utc_now - last_update).total_seconds()
        ),
    }


ROUTES: base.Routes = {
    "/health": (page, ["GET"]),
    "/h/health/refresh": (refresh, ["POST"]),
    "/h/health/i/<path:uri>/ignore": (ignore, ["PUT"]),
}
