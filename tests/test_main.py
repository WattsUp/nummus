from __future__ import annotations

import io
import subprocess
from unittest import mock

from nummus import commands, main, version
from tests.base import TestBase


class TestMain(TestBase):
    def test_entrypoints(self) -> None:
        # Check can execute entrypoint
        with subprocess.Popen(  # noqa: S603
            ["nummus", "--version"],  # noqa: S607
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            stdout, stderr = process.communicate()
            stdout = stdout.decode().strip("\r\n").strip("\n")
            stderr = stderr.decode().strip("\r\n").strip("\n")
            self.assertEqual(stderr, "")
            self.assertEqual(stdout, version.__version__)

    def test_unlock(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")

        # Try unlocking non-existent Portfolio
        args = ["--portfolio", str(path), "unlock"]
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            rc = main.main(args)
        self.assertNotEqual(rc, 0)

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.Create(path, None, force=False, no_encrypt=True).run()

        args = ["--portfolio", str(path), "unlock"]
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = main.main(args)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        self.assertIn("Portfolio is unlocked", fake_stdout)
