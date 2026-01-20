"""Flask extension."""

from __future__ import annotations

import datetime
import functools
import os
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import flask
import flask_login
import prometheus_client
import prometheus_flask_exporter
import prometheus_flask_exporter.multiprocess

from nummus import controllers
from nummus import exceptions as exc
from nummus import utils, web_assets
from nummus.controllers import (
    accounts,
    allocation,
    assets,
    auth,
    base,
    budgeting,
    common,
    emergency_fund,
    health,
    import_file,
    income,
    labels,
    net_worth,
    performance,
    settings,
    spending,
    transaction_categories,
    transactions,
)
from nummus.models.config import Config, ConfigKey
from nummus.portfolio import Portfolio
from nummus.version import __version__

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

        self._add_routes(app)
        web_assets.build_bundles(app)
        self._init_auth(app, self._portfolio)
        self._init_jinja_env(app.jinja_env)
        self._init_metrics(app)

        # Inject common variables into templates
        args: dict[str, dict[str, object]] = {
            "url_args": {},
        }
        app.context_processor(lambda: args)

    @classmethod
    def _open_portfolio(cls, config: dict[str, object]) -> Portfolio:
        s = config.get("PORTFOLIO", "~/.nummus/portfolio.db")
        if not isinstance(s, str):
            raise TypeError
        path = Path(s).expanduser().absolute()

        key = config.get("KEY")
        if key is None:
            path_key = config.get("KEY_PATH")
            path_key = (
                Path(path_key).expanduser().absolute()
                if isinstance(path_key, str)
                else None
            )
            if path_key and path_key.exists():
                key = path_key.read_text("utf-8").strip()
        elif not isinstance(key, str):
            raise TypeError

        return Portfolio(path, key)

    @classmethod
    def _add_routes(cls, app: flask.Flask) -> None:
        module = [
            accounts,
            allocation,
            assets,
            auth,
            budgeting,
            common,
            emergency_fund,
            health,
            import_file,
            income,
            net_worth,
            performance,
            settings,
            spending,
            labels,
            transactions,
            transaction_categories,
        ]
        n_trim = len(controllers.__name__) + 1
        urls: set[str] = set()
        for m in module:
            routes: base.Routes = m.ROUTES
            for url, (view_func, methods) in routes.items():
                endpoint = f"{m.__name__[n_trim:]}.{view_func.__name__}"
                if url in urls:  # pragma: no cover
                    raise exc.DuplicateURLError(url, endpoint)
                if url.startswith("/d/") and not app.debug:
                    continue
                urls.add(url)
                app.add_url_rule(url, endpoint, view_func, methods=methods)

    @classmethod
    def _init_auth(cls, app: flask.Flask, p: Portfolio) -> None:
        with p.begin_session():
            secret_key = Config.fetch(ConfigKey.SECRET_KEY)

        app.secret_key = secret_key
        config: dict[str, object] = app.config
        config["SESSION_COOKIE_SECURE"] = True
        config["SESSION_COOKIE_HTTPONLY"] = True
        config["SESSION_COOKIE_SAMESITE"] = "Lax"
        config["REMEMBER_COOKIE_SECURE"] = True
        config["REMEMBER_COOKIE_HTTPONLY"] = True
        config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
        config["REMEMBER_COOKIE_DURATION"] = datetime.timedelta(days=28)
        app.after_request(base.update_client_timezone)
        app.after_request(base.change_redirect_to_htmx)

        login_manager = flask_login.LoginManager()
        login_manager.init_app(app)
        login_manager.user_loader(auth.get_user)
        login_manager.login_view = "auth.page_login"

        if p.is_encrypted:
            # Only can have authentiation with encrypted portfolio
            app.before_request(auth.default_login_required)

    @classmethod
    def _init_jinja_env(cls, env: jinja2.Environment) -> None:
        env.filters["seconds"] = utils.format_seconds
        env.filters["days"] = utils.format_days
        env.filters["days_abv"] = functools.partial(
            utils.format_days,
            labels=["days", "wks", "mos", "yrs"],
        )
        env.filters["comma"] = lambda x: f"{x:,.2f}"
        env.filters["qty"] = lambda x: f"{x:,.6f}"
        env.filters["no_emojis"] = utils.strip_emojis
        env.filters["tojson"] = base.ctx_to_json
        env.filters["input_value"] = lambda x: str(x or "").rstrip("0").rstrip(".")

        def percent(x: Decimal | float | object) -> str:
            if not isinstance(x, Decimal | float):
                raise TypeError
            return f"{x * 100:5.2f}%"

        env.filters["percent"] = percent

        def pnl_color(x: Decimal | float | object) -> str:
            if not x:
                return ""
            if not isinstance(x, Decimal | float):
                raise TypeError
            return "text-primary" if x > 0 else "text-error"

        env.filters["pnl_color"] = pnl_color

        def pnl_arrow(x: Decimal | float | object) -> str:
            if not x:
                return ""
            if not isinstance(x, Decimal | float):
                raise TypeError
            return "arrow_upward" if x > 0 else "arrow_downward"

        env.filters["pnl_arrow"] = pnl_arrow

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
