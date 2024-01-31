from __future__ import annotations

import functools
import io
import subprocess
from pathlib import Path
from unittest import mock

from nummus import commands
from nummus import custom_types as t
from nummus import main, portfolio, version
from tests.base import TestBase


class TestMain(TestBase):
    def _set_up_commands(self) -> None:
        """Set up mocked commands by replacing all commands with an argument logger."""
        self._original_commands = {}
        for name in dir(commands):
            # The real unlock is needed for all commands to work, skip mocking
            if name == "unlock":
                continue
            value = getattr(commands, name)
            if callable(value) and value.__module__.startswith("nummus"):
                self._original_commands[name] = value

        self._called_args: t.Strings = []
        self._called_kwargs: t.DictAny = {}

        def check_call(*args: t.Any, **kwargs: t.Any) -> None:
            self._called_args.clear()
            self._called_args.extend(args)
            self._called_kwargs.clear()
            self._called_kwargs.update(kwargs)

        for name in self._original_commands:
            setattr(commands, name, functools.partial(check_call, _func=name))

    def _tear_down_commands(self) -> None:
        """Revert mocked commands."""
        for name, value in self._original_commands.items():
            setattr(commands, name, value)

    def test_version(self) -> None:
        args = ["--version"]
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            self.assertRaises(SystemExit, main.main, args)
        fake_stdout = fake_stdout.getvalue()
        self.assertEqual(fake_stdout, version.__version__ + "\n")

    def test_no_command(self) -> None:
        args = []
        with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
            self.assertRaises(SystemExit, main.main, args)
        fake_stderr = fake_stderr.getvalue()
        self.assertIn("the following arguments are required: <command>", fake_stderr)

    def test_entrypoints(self) -> None:
        # Check can execute entrypoint
        with subprocess.Popen(
            ["nummus", "--version"],  # noqa: S603, S607
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            stdout, stderr = process.communicate()
            stdout = stdout.decode().strip("\r\n").strip("\n")
            stderr = stderr.decode().strip("\r\n").strip("\n")
            self.assertEqual(stderr, "")
            self.assertEqual(stdout, version.__version__)

    def test_create(self) -> None:
        home = Path("~").expanduser()
        path = self._TEST_ROOT.joinpath("portfolio.db")
        path_password = self._TEST_ROOT.joinpath(".password")
        try:
            self._set_up_commands()

            args = ["create"]
            main.main(args)
            self.assertListEqual(self._called_args, [])
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "create",
                    "path_db": home.joinpath(".nummus", "portfolio.db"),
                    "force": False,
                    "no_encrypt": False,
                    "path_password": None,
                },
            )

            args = ["create", "--no-encrypt"]
            main.main(args)
            self.assertListEqual(self._called_args, [])
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "create",
                    "path_db": home.joinpath(".nummus", "portfolio.db"),
                    "force": False,
                    "no_encrypt": True,
                    "path_password": None,
                },
            )

            args = [
                "--portfolio",
                str(path),
                "--pass-file",
                str(path_password),
                "create",
                "--force",
            ]
            main.main(args)
            self.assertListEqual(self._called_args, [])
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "create",
                    "path_db": path,
                    "force": True,
                    "no_encrypt": False,
                    "path_password": path_password,
                },
            )
        finally:
            self._tear_down_commands()

    def test_unlock(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")

        # Try unlocking non-existent Portfolio
        args = ["--portfolio", str(path), "unlock"]
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            rc = main.main(args)
        self.assertNotEqual(rc, 0)

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        args = ["--portfolio", str(path), "unlock"]
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = main.main(args)
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        self.assertIn("Portfolio is unlocked", fake_stdout)

    def test_import(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "import"]
            with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
                self.assertRaises(SystemExit, main.main, args)
            fake_stderr = fake_stderr.getvalue()
            self.assertIn("arguments are required: PATH", fake_stderr)

            paths = ["transactions.csv"]
            args = ["--portfolio", str(path), "import", *paths]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "import_files",
                    "paths": [Path(p) for p in paths],
                    "force": False,
                },
            )

            paths = ["transactions.csv", "statement-dir"]
            args = ["--portfolio", str(path), "import", *paths, "--force"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "import_files",
                    "paths": [Path(p) for p in paths],
                    "force": True,
                },
            )

        finally:
            self._tear_down_commands()

    def test_web(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "web"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            is_dev = (
                version.version_dict["branch"] != "master"
                or version.version_dict["distance"] != 0
                or version.version_dict["dirty"]
            )
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "run_web",
                    "host": "127.0.0.1",
                    "port": 8080,
                    "debug": is_dev,
                },
            )

            args = ["--portfolio", str(path), "web", "--debug"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {"_func": "run_web", "host": "127.0.0.1", "port": 8080, "debug": True},
            )

            host = "192.168.1.2"
            port = 80
            args = [
                "--portfolio",
                str(path),
                "web",
                "-H",
                host,
                "-P",
                str(port),
                "--no-debug",
            ]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {"_func": "run_web", "host": host, "port": port, "debug": False},
            )
        finally:
            self._tear_down_commands()

    def test_restore(self) -> None:
        home = Path("~").expanduser()
        path = self._TEST_ROOT.joinpath("portfolio.db")
        path_password = self._TEST_ROOT.joinpath(".password")
        try:
            self._set_up_commands()

            args = ["restore", "-l"]
            main.main(args)
            self.assertListEqual(self._called_args, [])
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "restore",
                    "path_db": home.joinpath(".nummus", "portfolio.db"),
                    "path_password": None,
                    "tar_ver": None,
                    "list_ver": True,
                },
            )

            tar_ver = self._RNG.integers(1, 100)
            args = ["restore", "-v", str(tar_ver)]
            main.main(args)
            self.assertListEqual(self._called_args, [])
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "restore",
                    "path_db": home.joinpath(".nummus", "portfolio.db"),
                    "path_password": None,
                    "tar_ver": tar_ver,
                    "list_ver": False,
                },
            )

            args = [
                "--portfolio",
                str(path),
                "--pass-file",
                str(path_password),
                "restore",
            ]
            main.main(args)
            self.assertListEqual(self._called_args, [])
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "restore",
                    "path_db": path,
                    "path_password": path_password,
                    "tar_ver": None,
                    "list_ver": False,
                },
            )
        finally:
            self._tear_down_commands()

    def test_backup(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "backup"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(self._called_kwargs, {"_func": "backup"})
        finally:
            self._tear_down_commands()

    def test_clean(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "clean"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(self._called_kwargs, {"_func": "clean"})
        finally:
            self._tear_down_commands()

    def test_update_assets(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "update-assets"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(self._called_kwargs, {"_func": "update_assets"})
        finally:
            self._tear_down_commands()

    def test_summarize(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "summarize"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "summarize",
                    "include_all": False,
                },
            )

            args = ["--portfolio", str(path), "summarize", "--include-all"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "summarize",
                    "include_all": True,
                },
            )
        finally:
            self._tear_down_commands()

    def test_health(self) -> None:
        path = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            commands.create(path, None, force=False, no_encrypt=True)

        try:
            self._set_up_commands()

            args = ["--portfolio", str(path), "health"]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "health_check",
                    "limit": 10,
                    "ignores": None,
                    "always_descriptions": False,
                    "no_ignores": False,
                    "clear_ignores": False,
                },
            )

            ignores = [self.random_string() for _ in range(3)]
            args = [
                "--portfolio",
                str(path),
                "health",
                "--desc",
                "--ignore",
                *ignores,
                "-l",
                "20",
            ]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "health_check",
                    "limit": 20,
                    "ignores": ignores,
                    "always_descriptions": True,
                    "no_ignores": False,
                    "clear_ignores": False,
                },
            )

            args = [
                "--portfolio",
                str(path),
                "health",
                "--no-ignores",
                "--clear-ignores",
            ]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                main.main(args)
            self.assertEqual(len(self._called_args), 1)
            self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
            self.assertDictEqual(
                self._called_kwargs,
                {
                    "_func": "health_check",
                    "limit": 10,
                    "ignores": None,
                    "always_descriptions": False,
                    "no_ignores": True,
                    "clear_ignores": True,
                },
            )

        finally:
            self._tear_down_commands()
