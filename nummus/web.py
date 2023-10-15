"""Web server for nummus."""
from __future__ import annotations

import datetime
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING

import flask
import flask_assets
import gevent.pywsgi
import pytailwindcss
import webassets.filter
from colorama import Back, Fore
from OpenSSL import crypto

from nummus import controllers, portfolio, utils, version

if TYPE_CHECKING:
    import io


class Handler(gevent.pywsgi.WSGIHandler):
    """Custom WSGIHandler, mainly for request formatting."""

    REQ_TIME_BAD = 0.15
    REQ_TIME_WARN = 0.075

    _HTTP_CODE_COLORS = types.MappingProxyType(
        {
            2: Fore.GREEN,
            3: Fore.CYAN,
            4: Fore.YELLOW,
            5: Fore.RED,
        },
    )

    def format_request(self) -> str:
        """Format request as a single line.

        Returns:
            [client address] [now] [delta t] [method] [endpoint] [HTTP ver] [len]
        """
        now = datetime.datetime.now().replace(microsecond=0)
        length = "[len]" if self.response_length is None else f"{self.response_length}B"

        if self.time_finish:
            delta = self.time_finish - self.time_start
            if delta > self.REQ_TIME_BAD:
                delta = f"{Fore.RED}{delta:.6f}s{Fore.RESET}"
            elif delta > self.REQ_TIME_WARN:
                delta = f"{Fore.YELLOW}{delta:.6f}s{Fore.RESET}"
            else:
                delta = f"{Fore.GREEN}{delta:.6f}s{Fore.RESET}"
        else:
            delta = "[delta t]"

        if self.client_address is None:
            client_address = "[client address]"
        elif isinstance(self.client_address, tuple):
            client_address = self.client_address[0]
        else:
            client_address = self.client_address

        if self.requestline is None:
            method = "[method]"
            endpoint = "[endpoint]"
            http_ver = "[HTTP ver]"
        else:
            method, endpoint, http_ver = self.requestline.split(" ")
            if method == "GET":
                method = f"{Fore.CYAN}{method}{Fore.RESET}"
            elif method == "POST":
                method = f"{Fore.GREEN}{method}{Fore.RESET}"
            elif method == "PUT":
                method = f"{Fore.YELLOW}{method}{Fore.RESET}"
            elif method == "DELETE":
                method = f"{Fore.RED}{method}{Fore.RESET}"
            elif method == "OPTIONS":
                method = f"{Fore.BLUE}{method}{Fore.RESET}"
            elif method == "HEAD":
                method = f"{Fore.MAGENTA}{method}{Fore.RESET}"
            elif method == "PATCH":
                method = f"{Fore.BLACK}{Back.GREEN}{method}{Fore.RESET}{Back.RESET}"
            elif method == "TRACE":
                method = f"{Fore.BLACK}{Back.WHITE}{method}{Fore.RESET}{Back.RESET}"

            if endpoint.startswith("/h/"):
                endpoint = f"{Fore.CYAN}{endpoint}{Fore.RESET}"
            elif endpoint.startswith("/static/"):
                endpoint = f"{Fore.MAGENTA}{endpoint}{Fore.RESET}"
            else:
                endpoint = f"{Fore.GREEN}{endpoint}{Fore.RESET}"

        code = self.code
        if code is None:
            code = "[status]"
        else:
            c = self._HTTP_CODE_COLORS.get(code // 100, Fore.MAGENTA)
            code = f"{c}{code}{Fore.RESET}"

        return (
            f"{client_address} [{now}] {delta} "
            f"{method} {endpoint} {http_ver} {length} {code}"
        )


class TailwindCSSFilter(webassets.filter.Filter):
    """webassets Filter for running tailwindcss over."""

    def output(self, _in: io.StringIO, out: io.StringIO, **_) -> None:
        """Run filter and generate output file.

        Args:
            out: Output buffer
        """
        path_web = Path(__file__).parent.resolve()
        path_config = path_web.joinpath("static", "tailwind.config.js")
        path_in = path_web.joinpath("static", "src", "main.css")

        args = ["-c", str(path_config), "-i", str(path_in), "--minify"]
        built_css = pytailwindcss.run(args, auto_install=True)
        out.write(built_css)


class Server:
    """HTTP server that serves a nummus Portfolio."""

    def __init__(
        self,
        p: portfolio.Portfolio,
        host: str,
        port: int,
        *,
        debug: bool = False,
    ) -> None:
        """Initialize Server.

        Args:
            p: Portfolio to serve
            host: IP to bind to
            port: Network port to bind to
            debug: True will run Flask in debug mode
        """
        self._portfolio = p

        self._app = flask.Flask(__name__)

        # HTML pages routing
        controllers.add_routes(self._app)

        # Add Portfolio to context for controllers
        with self._app.app_context():
            flask.current_app.portfolio = p

        # Enable debugger and reloader when debug
        self._app.debug = debug
        if debug:
            print(f"{Fore.MAGENTA}Running in debug mode")

        # Inject common variables into templates
        self._app.context_processor(lambda: {"version": version.__version__})

        # Setup environment and static file bundles
        env_assets = flask_assets.Environment(self._app)

        bundle_css = flask_assets.Bundle(
            "src/main.css",
            output="dist/main.css",
            filters=(TailwindCSSFilter,),
        )
        env_assets.register("css", bundle_css)
        bundle_css.build()

        bundle_js = flask_assets.Bundle(
            "src/*.js",
            output="dist/main.js",
            filters=None if self._app.debug else "jsmin",
        )
        env_assets.register("js", bundle_js)
        bundle_js.build()

        self._app.jinja_env.filters["money"] = utils.format_financial
        self._app.jinja_env.filters["days"] = utils.format_days
        self._app.jinja_env.filters["comma"] = lambda x: f"{x:,.2f}"

        if not p.ssl_cert_path.exists():
            print(
                f"{Fore.RED}No SSL certificate found at {p.ssl_cert_path}",
                file=sys.stderr,
            )
            print(f"{Fore.MAGENTA}Generating self-signed certificate")
            self.generate_ssl_cert(p.ssl_cert_path, p.ssl_key_path)
            print("Please install certificate in web browser")

        # Check for self-signed SSL cert
        if self.is_ssl_cert_self_signed(p.ssl_cert_path):
            buf = (
                f"{Fore.YELLOW}SSL certificate appears to be self-signed at "
                f"{p.ssl_cert_path}\n"
                "Replace with real certificate to disable this warning"
            )
            print(buf, file=sys.stderr)

        self._server = gevent.pywsgi.WSGIServer(
            (host, port),
            self._app,
            certfile=p.ssl_cert_path,
            keyfile=p.ssl_key_path,
            handler_class=Handler,
        )

    def run(self) -> None:
        """Start and run the server."""
        url = f"https://localhost:{self._server.server_port}"
        print(f"{Fore.GREEN}nummus running on {url} (Press CTRL+C to quit)")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print(f"{Fore.YELLOW}Shutting down on interrupt")
            if self._server.started:
                self._server.stop()
        finally:
            now = datetime.datetime.now().isoformat(timespec="seconds")
            print(f"{Fore.YELLOW}nummus web shutdown at {now}")

    @staticmethod
    def generate_ssl_cert(path_cert: Path, path_key: Path) -> None:
        """Generate a self-signed SSL certificate.

        Args:
            path_cert: Path to SSL certificate
            path_key: Path to SSL certificate signing key
        """
        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, 4096)

        cert = crypto.X509()
        cert.set_version(2)  # Version x509v3 for SAN
        cert.get_subject().CN = "localhost"
        san_list = ["DNS:localhost"]
        ext = crypto.X509Extension(
            type_name=b"subjectAltName",
            critical=False,
            value=", ".join(san_list).encode(),
        )
        cert.add_extensions([ext])
        cert.set_serial_number(0)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)  # 10 yrs in seconds
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(key)
        cert.sign(key, "sha512")

        with path_cert.open("wb") as file:
            file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with path_key.open("wb") as file:
            file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

        path_cert.chmod(0o600)
        path_key.chmod(0o600)

    @staticmethod
    def is_ssl_cert_self_signed(path_cert: Path) -> bool:
        """Check if SSL certificate is self-signed.

        Args:
            path_cert: Path to SSL certificate

        Returns:
            True if CN=localhost, False otherwise
        """
        with path_cert.open("rb") as file:
            buf = file.read()
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, buf)
        return cert.get_subject().CN == "localhost"
