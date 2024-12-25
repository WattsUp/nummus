from __future__ import annotations

import io
from pathlib import Path

import flask
import setuptools

from nummus import web_assets
from tests.base import TestBase


class TestWebAssets(TestBase):

    def test_tailwindcss_filter(self) -> None:
        f = web_assets.TailwindCSSFilter()

        out = io.StringIO()
        f.output(None, out)  # type: ignore[attr-defined]
        buf = out.getvalue()
        self.assertIn("/*! tailwindcss", buf)
        self.assertIn("*,:after,:before", buf)

    def test_build_bundles(self) -> None:
        app = flask.Flask(__name__, root_path=str(Path(web_assets.__file__).parent))

        path_dist = Path(web_assets.__file__).parent.joinpath("static", "dist")
        path_dist_css = path_dist.joinpath("main.css")
        path_dist_js = path_dist.joinpath("main.js")

        path_dist_css.unlink(missing_ok=True)
        path_dist_js.unlink(missing_ok=True)
        web_assets.build_bundles(app, debug=True)
        self.assertTrue(path_dist_css.exists())
        self.assertTrue(path_dist_js.exists())

        with path_dist_css.open("r", encoding="utf-8") as file:
            buf = file.read()
        self.assertIn("/*! tailwindcss", buf)
        self.assertIn("*,:after,:before", buf)

        with path_dist_js.open("r", encoding="utf-8") as file:
            buf = file.read()
        # With debug, there should be comments
        self.assertIn("/**", buf)

        web_assets.build_bundles(app, debug=False)
        self.assertTrue(path_dist_css.exists())
        self.assertTrue(path_dist_js.exists())

        with path_dist_css.open("r", encoding="utf-8") as file:
            buf = file.read()
        self.assertIn("/*! tailwindcss", buf)
        self.assertIn("*,:after,:before", buf)

        with path_dist_js.open("r", encoding="utf-8") as file:
            buf = file.read()
        # Without debug, there should not be comments
        self.assertNotIn("/**", buf)

    def test_build_assets(self) -> None:
        path_dist = Path(web_assets.__file__).parent.joinpath("static", "dist")
        path_dist_css = path_dist.joinpath("main.css")
        path_dist_js = path_dist.joinpath("main.js")

        path_dist_css.unlink(missing_ok=True)
        path_dist_js.unlink(missing_ok=True)

        dist = setuptools.Distribution()
        builder = web_assets.BuildAssets(dist)
        builder.packages = None
        builder.run()
        self.assertTrue(path_dist_css.exists())
        self.assertTrue(path_dist_js.exists())

        with path_dist_css.open("r", encoding="utf-8") as file:
            buf = file.read()
        self.assertIn("/*! tailwindcss", buf)
        self.assertIn("*,:after,:before", buf)

        with path_dist_js.open("r", encoding="utf-8") as file:
            buf = file.read()
        # Without debug, there should not be comments
        self.assertNotIn("/**", buf)
