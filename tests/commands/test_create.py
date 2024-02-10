from __future__ import annotations

import io
from unittest import mock

from colorama import Fore

from nummus import encryption, portfolio
from nummus.commands import create_, unlock_
from tests.base import TestBase


class TestCommands(TestBase):
    def test_create_unencrypted(self) -> None:
        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = create_.utils.getpass.getpass

        queue: list[str] = []

        def mock_input(to_print: str) -> str:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = mock_input

            path_db = self._TEST_ROOT.joinpath("portfolio.db")
            path_salt = path_db.with_suffix(".nacl")
            path_password = self._TEST_ROOT.joinpath(".password")
            key = self.random_string()
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"  {key}  \n\n")

            # Create unencrypted
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(path_db, None, force=False, no_encrypt=True)
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio created at {path_db}\n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertFalse(path_salt.exists(), "Salt unexpectedly exists")

            # Check portfolio is unencrypted
            with path_db.open("rb") as file:
                buf = file.read()
                target = b"SQLite format 3"
                self.assertEqual(buf[: len(target)], target)
                buf = None  # Clear local buffer

            # Fail to overwrite
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(path_db, None, force=False, no_encrypt=True)
            fake_stdout = fake_stdout.getvalue()
            self.assertIn(f"Cannot overwrite portfolio at {path_db}", fake_stdout)
            self.assertNotEqual(rc, 0)

            # Overwrite
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(path_db, None, force=True, no_encrypt=True)
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio created at {path_db}\n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertFalse(path_salt.exists(), "Salt unexpectedly exists")

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = original_get_pass

    def test_unlock_unencrypted(self) -> None:
        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = create_.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = mock_input  # type: ignore[attr-defined]

            path_db = self._TEST_ROOT.joinpath("portfolio.db")

            # Non-existent Portfolio
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create\n"
            )
            self.assertEqual(fake_stdout, target)

            # Create and unlock unencrypted Portfolio
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                create_.create(path_db, None, force=False, no_encrypt=True)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, None)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = original_get_pass

    def test_unlock_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = create_.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = mock_input  # type: ignore[attr-defined]

            path_db = self._TEST_ROOT.joinpath("portfolio.db")

            # Create and unlock encrypted Portfolio
            key = self.random_string()
            queue = [key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                create_.create(path_db, None, force=True, no_encrypt=False)
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
                p = unlock_.unlock(path_db, path_password)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"Please enter password: \n{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Password file does exist
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"{key}\n")
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, path_password)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Password file does exist but incorrect
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"not the {key}\n")
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, path_password)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.RED}Could not decrypt with password file\n"
            self.assertEqual(fake_stdout, target)

            # No password file at all
            queue = [key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, None)
            self.assertIsNotNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = f"Please enter password: \n{Fore.GREEN}Portfolio is unlocked\n"
            self.assertEqual(fake_stdout, target)

            # Cancel entry
            queue = [None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, None)
            self.assertIsNone(p)

            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \n"
            self.assertEqual(fake_stdout, target)

            # 3 failed attempts
            queue = ["bad", "still wrong", "not going to work"]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                p = unlock_.unlock(path_db, None)
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
            create_.utils.getpass.getpass = original_get_pass

    def test_create_encrypted(self) -> None:
        if not encryption.AVAILABLE:
            self.skipTest("Encryption is not installed")

        original_input = mock.builtins.input  # type: ignore[attr-defined]
        original_get_pass = create_.utils.getpass.getpass

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 1:
                return queue[0]
            return queue.pop(0)

        try:
            mock.builtins.input = mock_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = mock_input

            path_db = self._TEST_ROOT.joinpath("portfolio.db")
            path_salt = path_db.with_suffix(".nacl")
            path_password = self._TEST_ROOT.joinpath(".password")
            key = self.random_string()
            with path_password.open("w", encoding="utf-8") as file:
                file.write(f"  {key}  \n\n")

            # Create encrypted
            queue = []
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(
                    path_db,
                    path_password,
                    force=False,
                    no_encrypt=False,
                )
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Portfolio created at {path_db}\n"
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(path_salt.exists(), "Salt does not exist")

            # Check password is correct
            portfolio.Portfolio(path_db, key)

            # Create encrypted
            queue = [key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(
                    path_db,
                    path_password.with_suffix(".nonexistent"),
                    force=True,
                    no_encrypt=False,
                )
            fake_stdout = fake_stdout.getvalue()
            target = (
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.GREEN}Portfolio created at {path_db}\n"
            )
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(path_salt.exists(), "Salt does not exist")

            # Check password is correct
            portfolio.Portfolio(path_db, key)

            # Create encrypted
            queue = [self.random_string(7), key, key + "typo", key, key]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(path_db, None, force=True, no_encrypt=False)
            fake_stdout = fake_stdout.getvalue()
            target = (
                "Please enter password: \n"
                f"{Fore.RED}Password must be at least 8 characters\n"
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.RED}Passwords must match\n"
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.GREEN}Portfolio created at {path_db}\n"
            )
            self.assertEqual(fake_stdout, target)
            self.assertEqual(rc, 0)
            self.assertTrue(path_db.exists(), "Portfolio does not exist")
            self.assertTrue(path_salt.exists(), "Salt does not exist")

            # Check password is correct
            portfolio.Portfolio(path_db, key)

            # Cancel on first prompt
            queue = [None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(path_db, None, force=True, no_encrypt=False)
            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertNotEqual(rc, 0)

            # Cancel on second prompt
            queue = [key, None]
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = create_.create(path_db, None, force=True, no_encrypt=False)
            fake_stdout = fake_stdout.getvalue()
            target = "Please enter password: \nPlease confirm password: \n"
            self.assertEqual(fake_stdout, target)
            self.assertNotEqual(rc, 0)

        finally:
            mock.builtins.input = original_input  # type: ignore[attr-defined]
            create_.utils.getpass.getpass = original_get_pass
