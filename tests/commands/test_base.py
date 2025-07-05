from __future__ import annotations

import io
from typing import TYPE_CHECKING
from unittest import mock

from colorama import Fore

from nummus import encryption, portfolio
from nummus.commands import base
from nummus.models import Config, ConfigKey
from tests.base import TestBase

if TYPE_CHECKING:
    import argparse


class MockCommand(base.BaseCommand):

    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        _ = parser

    def run(self) -> int:
        return 0


class Testbase(TestBase):
    def test_unlock_unencrypted(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            self.assertRaises(
                SystemExit,
                MockCommand,
                path_db,
                None,
            )
        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create\n"
        self.assertEqual(fake_stdout, target)

        # No issues if not unlocking
        MockCommand(path_db, None, do_unlock=False)

        # Create and unlock unencrypted Portfolio
        portfolio.Portfolio.create(path_db, None)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            p = base.BaseCommand._unlock(path_db, None)  # noqa: SLF001
        if p is None:
            self.fail("portfolio is None")

        fake_stdout = fake_stdout.getvalue()
        target = ""
        self.assertEqual(fake_stdout, target)

        # Force migration required
        with p.begin_session() as s:
            # Good, now reset version
            s.query(Config).where(Config.key == ConfigKey.VERSION).update(
                {"value": "0.0.0"},
            )
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            self.assertRaises(SystemExit, MockCommand, path_db, None)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.RED}Portfolio requires migration to v0.2.0\n"
            f"{Fore.YELLOW}Run nummus migrate to resolve\n"
        )
        self.assertEqual(fake_stdout, target)

    def test_unlock_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)  # noqa: T201
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        # Create and unlock encrypted Portfolio
        key = self.random_string()
        portfolio.Portfolio.create(path_db, key)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        self.assertTrue(
            portfolio.Portfolio.is_encrypted_path(path_db),
            "Portfolio is not encrypted",
        )

        queue = [key]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            p = base.BaseCommand._unlock(path_db, None)  # noqa: SLF001
        self.assertIsNotNone(p)

        fake_stdout = fake_stdout.getvalue()
        target = "Please enter password: \n"
        self.assertEqual(fake_stdout, target)

        queue = []
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            p = base.BaseCommand._unlock(path_db, key)  # noqa: SLF001
        self.assertIsNotNone(p)

        fake_stdout = fake_stdout.getvalue()
        target = ""
        self.assertEqual(fake_stdout, target)

        queue = []
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            self.assertRaises(
                SystemExit,
                base.BaseCommand._unlock,  # noqa: SLF001
                path_db,
                "not the " + key,
            )

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.RED}Could not decrypt with password file\n"
        self.assertEqual(fake_stdout, target)

        queue = [key]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            p = base.BaseCommand._unlock(path_db, None)  # noqa: SLF001
        self.assertIsNotNone(p)

        fake_stdout = fake_stdout.getvalue()
        target = "Please enter password: \n"
        self.assertEqual(fake_stdout, target)

        # Cancel entry
        queue = [None]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            self.assertRaises(
                SystemExit,
                base.BaseCommand._unlock,  # noqa: SLF001
                path_db,
                None,
            )

        fake_stdout = fake_stdout.getvalue()
        target = "Please enter password: \n"
        self.assertEqual(fake_stdout, target)

        # 3 failed attempts
        queue = ["bad", "still wrong", "not going to work"]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            self.assertRaises(
                SystemExit,
                base.BaseCommand._unlock,  # noqa: SLF001
                path_db,
                None,
            )

        fake_stdout = fake_stdout.getvalue()
        target = (
            "Please enter password: \n"
            f"{Fore.RED}Incorrect password\n"
            "Please enter password: \n"
            f"{Fore.RED}Incorrect password\n"
            "Please enter password: \n"
            f"{Fore.RED}Incorrect password\n"
            f"{Fore.RED}Too many incorrect attempts\n"
        )
        self.assertEqual(fake_stdout, target)

        path_password = path_db.with_suffix(".password")
        with path_password.open("w", encoding="utf-8") as file:
            file.write(key)

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            MockCommand(path_db, path_password)
        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio is unlocked\n"
        self.assertEqual(fake_stdout, target)
