"""Web assets manager."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import flask
import flask_assets
import webassets.filter
from setuptools.command import build_py

try:
    import jsmin
    import pytailwindcss
except ImportError:
    pytailwindcss = None
    jsmin = None

if TYPE_CHECKING:
    import io

    import setuptools


class TailwindCSSFilter(webassets.filter.Filter):
    """webassets Filter for running tailwindcss over."""

    def output(self, _in: io.StringIO, out: io.StringIO, **_) -> None:
        """Run filter and generate output file.

        Args:
            out: Output buffer
        """
        if pytailwindcss is None:
            raise NotImplementedError
        path_web = Path(__file__).parent.resolve()
        path_config = path_web.joinpath("static", "tailwind.config.js")
        path_in = path_web.joinpath("static", "src", "main.css")

        args = ["-c", str(path_config), "-i", str(path_in), "--minify"]
        built_css = pytailwindcss.run(args, auto_install=True)
        out.write(built_css)


def build_bundles(app: flask.Flask, *, debug: bool, force: bool = False) -> None:
    """Build asset bundles.

    Args:
        app: Flask app to build for
        debug: True will not run jsmin filter
        force: True will force build bundles
    """
    env_assets = flask_assets.Environment(app)
    stub_dist_css = "dist/main.css"
    stub_dist_js = "dist/main.js"

    path_static = Path(app.static_folder or "static")
    path_src = path_static.joinpath("src")
    path_dist_css = path_static.joinpath(stub_dist_css)
    path_dist_js = path_static.joinpath(stub_dist_js)
    if not path_src.exists():  # pragma: no cover
        # Too difficult to test for simple logic, skip tests
        if not path_dist_css.exists() or not path_dist_js.exists():
            msg = "Static source folder does not exists and neither does dist"
            raise FileNotFoundError(msg)
        if debug:
            msg = "Static source folder does not exists but running in debug"
            raise FileNotFoundError(msg)

        # Use dist directly
        env_assets.register("css", stub_dist_css)
        env_assets.register("js", stub_dist_js)
        return

    bundle_css = flask_assets.Bundle(
        "src/*.css",
        output=stub_dist_css,
        filters=None if pytailwindcss is None else (TailwindCSSFilter,),
    )
    env_assets.register("css", bundle_css)
    bundle_css.build(force=force)

    bundle_js = flask_assets.Bundle(
        # hammer.js needs to be before chart.js
        "src/3rd-party/hammer.js",
        # chart.js needs to be before plugins
        "src/3rd-party/chart.min.js",
        "src/*.js",
        "src/**/*.js",
        output=stub_dist_js,
        filters=None if jsmin is None or debug else "jsmin",
    )
    env_assets.register("js", bundle_js)
    bundle_js.build(force=force)


class BuildAssets(build_py.build_py):
    """Build assets during build command."""

    def __init__(self, dist: setuptools.Distribution) -> None:
        """Initialize BuildAssets."""
        if pytailwindcss is None or jsmin is None:  # pragma: no cover
            msg = "Filters not installed for BuildAssets"
            raise ImportError(msg)
        super().__init__(dist)

    def run(self) -> None:
        """Build assets during build command."""
        app = flask.Flask(__name__, root_path=str(Path(__file__).parent))
        build_bundles(app, debug=False, force=True)
        return super().run()
