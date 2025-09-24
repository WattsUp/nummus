"""Flask extension."""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import TYPE_CHECKING

import flask
import flask_login
import prometheus_client
import prometheus_flask_exporter
import prometheus_flask_exporter.multiprocess

from nummus import __version__, controllers
from nummus import exceptions as exc
from nummus import utils, web_assets
from nummus.controllers import auth, base
from nummus.models import Config, ConfigKey
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    import jinja2


class FlaskExtension:
    """nummus flask extension."""

    def init_app(self, app: flask.Flask) -> None:
        """Initialize app with extension.

        Args:
            app: Flask app to initialize

        """
        config = flask.Config(app.root_path)
        config.from_prefixed_env("NUMMUS")
        self._portfolio = self._open_portfolio(config)

        self._original_url_for = app.url_for
        app.url_for = self.url_for

        controllers.add_routes(app)
        web_assets.build_bundles(app)
        self._init_auth(app, self._portfolio)
        self._init_jinja_env(app.jinja_env)
        self._init_metrics(app)

        # Inject common variables into templates
        app.context_processor(
            lambda: {
                "url_args": {},
            },
        )

    @classmethod
    def _open_portfolio(cls, config: flask.Config) -> Portfolio:
        path = (
            Path(
                config.get("PORTFOLIO", "~/.nummus/portfolio.db"),
            )
            .expanduser()
            .absolute()
        )

        key = config.get("KEY")
        if key is None:
            path_key = config.get("KEY_PATH")
            path_key = Path(path_key).expanduser().absolute() if path_key else None
            if path_key and path_key.exists():
                with path_key.open("r", encoding="utf-8") as file:
                    key = file.read().strip()

        return Portfolio(path, key)

    @classmethod
    def _init_auth(cls, app: flask.Flask, p: Portfolio) -> None:
        with p.begin_session() as s:
            secret_key = (
                s.query(Config.value).where(Config.key == ConfigKey.SECRET_KEY).scalar()
            )
            if secret_key is None:  # pragma: no cover
                msg = "Config SECRET_KEY was not found"
                raise exc.ProtectedObjectNotFoundError(msg)

        app.secret_key = secret_key
        app.config.update(
            SESSION_COOKIE_SECURE=True,
            SESSION_COOKIE_HTTPONLY=True,
            SESSION_COOKIE_SAMESITE="Lax",
            REMEMBER_COOKIE_SECURE=True,
            REMEMBER_COOKIE_HTTPONLY=True,
            REMEMBER_COOKIE_SAMESITE="Lax",
            REMEMBER_COOKIE_DURATION=datetime.timedelta(days=28),
        )
        app.after_request(base.update_client_timezone)
        app.after_request(base.change_redirect_to_htmx)

        login_manager = flask_login.LoginManager()
        login_manager.init_app(app)
        login_manager.user_loader(auth.get_user)
        # LoginManager.login_view not typed to str | None
        login_manager.login_view = "auth.page_login"  # type: ignore[attr-defined]

        if p.is_encrypted:
            # Only can have authentiation with encrypted portfolio
            app.before_request(auth.default_login_required)

    @classmethod
    def _init_jinja_env(cls, env: jinja2.Environment) -> None:
        env.filters["money"] = utils.format_financial
        env.filters["money0"] = lambda x: utils.format_financial(x, 0)
        env.filters["money6"] = lambda x: utils.format_financial(x, 6)
        env.filters["seconds"] = utils.format_seconds
        env.filters["days"] = utils.format_days
        env.filters["days_abv"] = lambda x: utils.format_days(
            x,
            ["days", "wks", "mos", "yrs"],
        )
        env.filters["comma"] = lambda x: f"{x:,.2f}"
        env.filters["qty"] = lambda x: f"{x:,.6f}"
        env.filters["percent"] = lambda x: f"{x * 100:5.2f}%"
        env.filters["pnl_color"] = lambda x: (
            "" if x is None or x == 0 else ("text-primary" if x > 0 else "text-error")
        )
        env.filters["pnl_arrow"] = lambda x: (
            ""
            if x is None or x == 0
            else ("arrow_upward" if x > 0 else "arrow_downward")
        )
        env.filters["no_emojis"] = utils.strip_emojis
        env.filters["tojson"] = base.ctx_to_json
        env.filters["input_value"] = lambda x: str(x or "").rstrip("0").rstrip(".")

    @classmethod
    def _init_metrics(cls, app: flask.Flask) -> None:
        multiproc = "PROMETHEUS_MULTIPROC_DIR" in os.environ
        metrics_class = (
            prometheus_flask_exporter.multiprocess.GunicornPrometheusMetrics
            if multiproc
            else prometheus_flask_exporter.PrometheusMetrics
        )
        metrics = metrics_class(
            app,
            path="/metrics",
            excluded_paths=["/static", "/metrics", "/status"],
            group_by="endpoint",
            registry=(
                None
                if multiproc
                else prometheus_client.CollectorRegistry(auto_describe=True)
            ),
        )
        metrics.info("nummus_info", "nummus info", version=__version__)

    def url_for(
        self,
        /,
        endpoint: str,
        *,
        _anchor: str | None = None,
        _method: str | None = None,
        _scheme: str | None = None,
        _external: bool | None = None,
        **values: object,
    ) -> str:
        """Override flask.url_for.

        Returns:
            URL with better arg formatting

        """
        # Change snake case to kebab case
        # Change bools to "" if True, omit if False
        values = {
            k.replace("_", "-"): "" if isinstance(v, bool) else v
            for k, v in values.items()
            if not isinstance(v, str | bool | None) or v
        }
        return self._original_url_for(
            endpoint,
            _anchor=_anchor,
            _method=_method,
            _scheme=_scheme,
            _external=_external,
            **values,
        )

    @property
    def portfolio(self) -> Portfolio:
        """Portfolio flask is serving."""
        return self._portfolio


ext = FlaskExtension()
portfolio: Portfolio


def create_app() -> flask.Flask:
    """Create flask app.

    Returns:
        NummusApp

    """
    app = flask.Flask(__name__)
    ext.init_app(app)
    return app


def __getattr__(name: str) -> object:
    if name == "portfolio":
        return ext.portfolio
    msg = f"module {__name__} has no attribute {name}"
    raise AttributeError(msg)
