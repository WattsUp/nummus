"""Health controllers."""

from __future__ import annotations

import datetime
from collections import defaultdict
from typing import TYPE_CHECKING, TypedDict

import flask

from nummus import health_checks, portfolio, utils
from nummus.controllers import common
from nummus.models import Config, ConfigKey, HealthCheckIssue, YIELD_PER

if TYPE_CHECKING:
    from nummus.controllers.base import Routes


class HealthCheckContext(TypedDict):
    """Type definition for health check context."""

    name: str
    is_closed: bool
    description: str
    is_severe: bool
    issues: dict[str, str]


def ctx_checks(*, run: bool) -> dict[str, object]:
    """Get the context to build the health checks.

    Args:
        run: True will rerun health checks

    Returns:
        Dictionary HTML context
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    utc_now = datetime.datetime.now(datetime.timezone.utc)
    checks_open: list[str] = flask.session.get("checks_open", [])

    issues: dict[str, dict[str, str]] = defaultdict(dict)
    with p.begin_session() as s:
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

        if run:
            c = check_type(p)
            c.test()
            c_issues = c.issues
        else:
            c_issues = issues[check_type.name]

        checks.append(
            {
                "name": check_type.name,
                "is_closed": check_type.name not in checks_open,
                "description": check_type.description,
                "is_severe": check_type.is_severe,
                "issues": dict(sorted(c_issues.items(), key=lambda item: item[1])),
            },
        )
    return {
        "checks": checks,
        "last_update_ago": (
            None
            if last_update is None
            else utils.format_seconds((utc_now - last_update).total_seconds())
        ),
    }


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
        oob=True,
    )


def check(name: str) -> str:
    """PUT /h/health/c/<name>.

    Returns:
        string HTML response
    """
    is_open = "closed" not in flask.request.form

    checks_open: list[str] = flask.session.get("checks_open", [])
    checks_open = [x for x in checks_open if x != name]
    if is_open:
        checks_open.append(name)
    flask.session["checks_open"] = checks_open

    return flask.render_template(
        "health/checks.jinja",
        checks=ctx_checks(run=False),
        oob=True,
    )


def ignore(uri: str) -> str:
    """POST /h/health/i/<uri>/ignore.

    Args:
        uri: HealthCheckIssue uri to ignore

    Returns:
        string HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    with p.begin_session() as s:
        s.query(HealthCheckIssue).where(
            HealthCheckIssue.id_ == HealthCheckIssue.uri_to_id(uri),
        ).update({"ignore": True})

    return flask.render_template(
        "health/checks.jinja",
        checks=ctx_checks(run=False),
        oob=True,
    )


ROUTES: Routes = {
    "/health": (page, ["GET"]),
    "/h/health/refresh": (refresh, ["POST"]),
    "/h/health/c/<path:name>": (check, ["PUT"]),
    "/h/health/i/<path:uri>/ignore": (ignore, ["PUT"]),
}
