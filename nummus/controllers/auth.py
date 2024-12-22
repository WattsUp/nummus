"""Authentication controller."""

from __future__ import annotations

from typing import TYPE_CHECKING

import flask
import flask_login

from nummus import exceptions as exc
from nummus import portfolio
from nummus.controllers import common
from nummus.models import Config, ConfigKey

if TYPE_CHECKING:
    from collections.abc import Callable

    from nummus.controllers.base import Routes


def login_exempt(func: Callable) -> Callable:
    """Dectorator to exclude route from requiring authentication.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """
    func.login_exempt = True  # type: ignore[attr-defined]
    return func


def default_login_required() -> flask.Response | None:
    """Make all routes require login, use @login_exempt to exclude.

    Returns:
        Response if redirect is required
    """
    endpoint = flask.request.endpoint
    if not endpoint or endpoint.rsplit(".", 1)[-1] == "static":
        return None

    view = flask.current_app.view_functions[endpoint]
    if getattr(view, "login_exempt", False):
        return None

    return flask_login.login_required(lambda: None)()


class WebUser(flask_login.UserMixin):
    """Web user model."""

    # Only one user, for now?
    ID = "web"

    def __init__(self) -> None:
        """Initialize WebUser."""
        super().__init__()

        self.id = self.ID


def get_user(username: str) -> flask_login.UserMixin | flask_login.AnonymousUserMixin:
    """Load a user from name.

    Args:
        username: Username of user

    Returns:
        User object or Anonymous
    """
    if username != WebUser.ID:  # pragma: no cover
        # Don't need to test anonymous
        return flask_login.AnonymousUserMixin()
    return WebUser()


@login_exempt
def page_login() -> str:
    """GET /login.

    Returns:
        HTML response
    """
    next_url = flask.request.args.get("next")
    return flask.render_template(
        "auth/login.jinja",
        next_url=next_url,
    )


@login_exempt
def login() -> str | flask.Response:
    """POST /h/login.

    Returns:
        HTML response
    """
    with flask.current_app.app_context():
        p: portfolio.Portfolio = flask.current_app.portfolio  # type: ignore[attr-defined]

    form = flask.request.form
    password = form.get("password")

    if not password:
        return common.error("Password must not be blank")

    with p.get_session() as s:
        expected_encoded = (
            s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
        )
        if expected_encoded is None:  # pragma: no cover
            # Don't need to test ProtectedObjectNotFoundError
            msg = "Web user not found in portfolio"
            raise exc.ProtectedObjectNotFoundError(msg)

        expected = p.decrypt(expected_encoded)
        if password.encode() != expected:
            return common.error("Bad password")

        web_user = WebUser()
        flask_login.login_user(web_user)

        next_url = form.get("next")
        if next_url is None:
            return common.redirect(flask.url_for("dashboard.page"))
        return common.redirect(next_url)


def logout() -> str | flask.Response:
    """POST /h/logout.

    Returns:
        HTML response
    """
    flask_login.logout_user()
    return common.redirect(flask.url_for("auth.page_login"))


ROUTES: Routes = {
    "/login": (page_login, ["GET"]),
    "/h/login": (login, ["POST"]),
    "/h/logout": (logout, ["POST"]),
}
