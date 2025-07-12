"""Base web server for nummus."""

from __future__ import annotations

import datetime
import types
from pathlib import Path

import flask
import flask_login
import prometheus_client
import prometheus_flask_exporter
import prometheus_flask_exporter.multiprocess
from colorama import Back, Fore
from typing_extensions import override

from nummus import __version__, controllers
from nummus import exceptions as exc
from nummus import portfolio, utils
from nummus.controllers import auth, base
from nummus.models import Config, ConfigKey
from nummus.web import assets
from nummus.web import utils as web_utils

RESPONSE_TOO_SLOW = 0.15
RESPONSE_SLOW = 0.075
RESPONSE_TOO_LARGE = 1e6
RESPONSE_LARGE = 500e3

METHOD_COLORS = types.MappingProxyType(
    {
        "GET": (Fore.CYAN, ""),
        "POST": (Fore.GREEN, ""),
        "PUT": (Fore.YELLOW, ""),
        "DELETE": (Fore.RED, ""),
        "OPTIONS": (Fore.BLUE, ""),
        "HEAD": (Fore.MAGENTA, ""),
        "PATCH": (Fore.BLACK, Back.GREEN),
        "TRACE": (Fore.BLACK, Back.WHITE),
    },
)

HTTP_CODE_COLORS = types.MappingProxyType(
    {
        2: Fore.GREEN,
        3: Fore.CYAN,
        4: Fore.YELLOW,
        5: Fore.RED,
    },
)

PATH_COLORS = types.MappingProxyType(
    {
        "/h/": Fore.CYAN,
        "/static": Fore.MAGENTA,
        "/": Fore.GREEN,
    },
)


class NummusRequest(flask.Request):
    """flask Request for nummus."""

    @staticmethod
    def format(
        *,
        client_address: str,
        duration_s: float,
        method: str,
        path: str,
        length_bytes: int,
        status: int,
    ) -> str:
        """Format request for logger.

        Args:
            client_address: Address to client
            duration_s: Duration between request and response
            method: Request HTTP method
            path: Request path
            length_bytes: Size of response in bytes
            status: Response status code

        Returns:
            logger string
        """
        now = datetime.datetime.now().astimezone().replace(microsecond=0)

        if duration_s > RESPONSE_TOO_SLOW:
            duration = f"{Fore.RED}{duration_s:.3f}s{Fore.RESET}"
        elif duration_s > RESPONSE_SLOW:
            duration = f"{Fore.YELLOW}{duration_s:.3f}s{Fore.RESET}"
        else:
            duration = f"{Fore.GREEN}{duration_s:.3f}s{Fore.RESET}"

        c, b = METHOD_COLORS.get(method, ("", ""))
        method = f"{c}{b}{method}{c and Fore.RESET}{b and Back.RESET}"

        for partial, c in PATH_COLORS.items():
            if path.startswith(partial):
                path = f"{c}{path}{Fore.RESET}"
                break

        if length_bytes > RESPONSE_TOO_LARGE:
            length = f"{Fore.RED}{length_bytes}B{Fore.RESET}"
        elif length_bytes > RESPONSE_LARGE:
            length = f"{Fore.YELLOW}{length_bytes}B{Fore.RESET}"
        else:
            length = f"{Fore.GREEN}{length_bytes}B{Fore.RESET}"

        c = HTTP_CODE_COLORS.get(status // 100, Fore.MAGENTA)
        code = f"{c}{status}{Fore.RESET}"

        return f"{client_address} [{now}] {duration} {method} {path} {length} {code}"


class NummusApp(flask.Flask):
    """nummus flask app."""

    @override
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
        # Change snake case to kebab case
        # Change bools to "" if True, omit if False
        values = {
            k.replace("_", "-"): "" if isinstance(v, bool) else v
            for k, v in values.items()
            if not isinstance(v, str | bool | None) or v
        }
        return super().url_for(
            endpoint,
            _anchor=_anchor,
            _method=_method,
            _scheme=_scheme,
            _external=_external,
            **values,
        )


def create_flask_app(p: portfolio.Portfolio, *, debug: bool = False) -> flask.Flask:
    """Create the flask App.

    Args:
        p: Portfolio to serve
        debug: True will enable debug mode

    Returns:
        Created flask app

    Raises:
        ProtectedObjectNotFoundError: If SECRET_KEY is not found
    """
    path_root = Path(__file__).parent.parent.resolve()
    app = NummusApp(
        __name__,
        static_folder=str(path_root / "static"),
        template_folder=str(path_root / "templates"),
    )
    app.request_class = NummusRequest

    metrics_class = (
        prometheus_flask_exporter.PrometheusMetrics
        if debug
        else prometheus_flask_exporter.multiprocess.GunicornPrometheusMetrics
    )
    metrics = metrics_class(
        app,
        path="/metrics",
        excluded_paths=["/static", "/metrics"],
        group_by="endpoint",
        registry=(
            prometheus_client.CollectorRegistry(auto_describe=True) if debug else None
        ),
    )
    metrics.info("nummus_info", "nummus info", version=__version__)

    # HTML pages routing
    controllers.add_routes(app, debug=debug)

    # Add Portfolio to context for controllers
    with app.app_context():
        flask.current_app.portfolio = p  # type: ignore[attr-defined]

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
    app.after_request(base.change_redirect_to_htmx)

    login_manager = flask_login.LoginManager()
    login_manager.init_app(app)
    login_manager.user_loader(auth.get_user)
    login_manager.login_view = "auth.page_login"  # type: ignore[attr-defined]

    # Enable debugger and reloader when debug
    app.debug = debug

    # Inject common variables into templates
    app.context_processor(
        lambda: {
            "version": __version__,
            "current_year": datetime.datetime.now().astimezone().year,
            "url_args": {},
        },
    )
    if p.is_encrypted:
        # Only can have authentiation with encrypted portfolio
        app.before_request(auth.default_login_required)

    # Setup environment and static file bundles
    assets.build_bundles(app, debug=debug)

    app.jinja_env.filters["money"] = utils.format_financial
    app.jinja_env.filters["money0"] = lambda x: utils.format_financial(x, 0)
    app.jinja_env.filters["money6"] = lambda x: utils.format_financial(x, 6)
    app.jinja_env.filters["seconds"] = utils.format_seconds
    app.jinja_env.filters["days"] = utils.format_days
    app.jinja_env.filters["days_abv"] = lambda x: utils.format_days(
        x,
        ["days", "wks", "mos", "yrs"],
    )
    app.jinja_env.filters["comma"] = lambda x: f"{x:,.2f}"
    app.jinja_env.filters["qty"] = lambda x: f"{x:,.6f}"
    app.jinja_env.filters["percent"] = lambda x: f"{x * 100:5.2f}%"
    app.jinja_env.filters["pnl_color"] = lambda x: (
        "" if x is None or x == 0 else ("text-primary" if x > 0 else "text-error")
    )
    app.jinja_env.filters["pnl_arrow"] = lambda x: (
        "" if x is None or x == 0 else ("arrow_upward" if x > 0 else "arrow_downward")
    )
    app.jinja_env.filters["no_emojis"] = utils.strip_emojis
    app.jinja_env.filters["tojson"] = web_utils.ctx_to_json
    app.jinja_env.filters["input_value"] = (
        lambda x: str(x or "").rstrip("0").rstrip(".")
    )

    return app
