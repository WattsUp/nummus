"""Web assets manager."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import flask
import flask_assets
import pytailwindcss
import webassets.filter
from setuptools.command import build_py

if TYPE_CHECKING:
    import io


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


def build_bundles(app: flask.Flask, *, debug: bool, force: bool = False) -> None:
    """Build asset bundles.

    Args:
        app: Flask app to build for
        debug: True will not run jsmin filter
        force: True will force build bundles
    """
    env_assets = flask_assets.Environment(app)
    bundle_css = flask_assets.Bundle(
        "src/main.css",
        output="dist/main.css",
        filters=(TailwindCSSFilter,),
    )
    env_assets.register("css", bundle_css)
    bundle_css.build(force=force)

    bundle_js = flask_assets.Bundle(
        "src/*.js",
        "src/**/*.js",
        output="dist/main.js",
        filters=None if debug else "jsmin",
    )
    env_assets.register("js", bundle_js)
    bundle_js.build(force=force)


class BuildAssets(build_py.build_py):
    """Build assets during build command."""

    def run(self) -> None:
        """Build assets during build command."""
        app = flask.Flask(__name__, root_path=str(Path(__file__).parent))
        build_bundles(app, debug=False, force=True)
        return super().run()
