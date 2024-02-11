from __future__ import annotations

import io
from unittest import mock

from colorama import Fore

from nummus import encryption, portfolio
from nummus.commands import base, create
from tests.base import TestBase


class Testbase(TestBase):
    def test_unlock_unencrypted(self) -> None:
        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = base.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            base.utils.getpass.getpass = mock_input  # type: ignore[attr-defined]

            path_db = self._TEST_ROOT.joinpath("portfolio.db")

            # Non-existent Portfolio
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create\n"
            )
            self.assertEqual(fake_stdout, target)

            # Create and unlock unencrypted Portfolio
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                create.Create(path_db, None, force=False, no_encrypt=True).run()
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, None)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            base.utils.getpass.getpass = original_get_pass

    def test_unlock_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = base.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            base.utils.getpass.getpass = mock_input  # type: ignore[attr-defined]

            path_db = self._TEST_ROOT.joinpath("portfolio.db")

            # Create and unlock encrypted Portfolio
            key = self.random_string()
            queue = [key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                create.Create(path_db, None, force=True, no_encrypt=False).run()
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(
                portfolio.Portfolio.is_encrypted(path_db),
                "Portfolio is not encrypted",
            )

            # Password file does not exist
            path_password = self._TEST_ROOT.joinpath(".password")
            self.assertFalse(path_password.exists(), "Password does exist")
            queue = [key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, path_password)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"Please enter password: \n{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Password file does exist
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"{key}\n")
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, path_password)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Password file does exist but incorrect
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"not the {key}\n")
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, path_password)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.RED}Could not decrypt with password file\n"
            self.assertEqual(fake_stdout, target)

            # No password file at all
            queue = [key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, None)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"Please enter password: \n{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Cancel entry
            queue = [None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \n"
            self.assertEqual(fake_stdout, target)

            # 3 failed attempts
            queue = ["bad", "still wrong", "not going to work"]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = base.unlock(path_db, None)
            self.assertIsNone(p)

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

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            base.utils.getpass.getpass = original_get_pass
