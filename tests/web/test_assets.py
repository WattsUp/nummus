from __future__ import annotations

import io
from pathlib import Path

import flask
import setuptools

import nummus
from nummus.web import assets
from tests.base import TestBase


class TestWebAssets(TestBase):

    def test_tailwindcss_filter(self) -> None:
        f = assets.TailwindCSSFilter()

        out = io.StringIO()
        f.output(None, out)  # type: ignore[attr-defined]
        buf = out.getvalue()
        self.assertIn("/*! tailwindcss", buf)
        self.assertIn("*,:after,:before", buf)

    def test_jsmin_filter(self) -> None:
        f = assets.JSMinFilter()

        _in = io.StringIO("const abc = 123;  \nconst string = `${abc} = abc`")
        out = io.StringIO()
        f.output(_in, out)
        buf = out.getvalue()
        target = "const abc=123;const string=`${abc} = abc`"
        self.assertEqual(buf, target)

    def test_build_bundles(self) -> None:
        path_root = Path(nummus.__file__).parent.resolve()
        app = flask.Flask(__name__, root_path=str(path_root))

        path_dist = path_root / "static" / "dist"
        path_dist_css = path_dist / "main.css"
        path_dist_js = path_dist / "main.js"

        path_dist_css.unlink(missing_ok=True)
        path_dist_js.unlink(missing_ok=True)
        assets.build_bundles(app, debug=True)
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

        assets.build_bundles(app, debug=False)
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
        path_root = Path(nummus.__file__).parent.resolve()
        path_dist = path_root / "static" / "dist"
        path_dist_css = path_dist / "main.css"
        path_dist_js = path_dist / "main.js"

        path_dist_css.unlink(missing_ok=True)
        path_dist_js.unlink(missing_ok=True)

        dist = setuptools.Distribution()
        builder = assets.BuildAssets(dist)
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
