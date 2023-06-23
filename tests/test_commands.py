"""Test module nummus.commands
"""

from typing import List

import io
from unittest import mock

from colorama import Fore

from nummus import commands, portfolio

from tests.base import TestBase


class TestCommands(TestBase):
  """Test CLI commands
  """

  def test_create(self):
    original_input = mock.builtins.input
    original_get_pass = commands.common.getpass.getpass

    queue: List[str] = []

    def mock_input(to_print: str):
      print(to_print)
      if len(queue) == 1:
        return queue[0]
      return queue.pop(0)

    try:
      mock.builtins.input = mock_input
      commands.common.getpass.getpass = mock_input

      path_db = self._TEST_ROOT.joinpath("portfolio.db")
      path_config = path_db.with_suffix(".config")
      path_password = self._TEST_ROOT.joinpath(".password")
      key = self.random_string()
      with open(path_password, "w", encoding="utf-8") as file:
        file.write(f"  {key}  \n\n")

      # Create unencrypted
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, None, False, True)
      fake_stdout = fake_stdout.getvalue()
      self.assertEqual(fake_stdout, "")
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      # Check portfolio is unencrypted
      with open(path_db, "rb") as file:
        buf = file.read()
        target = b"SQLite format 3"
        self.assertEqual(target, buf[:len(target)])
        buf = None  # Clear local buffer

      # Fail to overwrite
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, None, False, True)
      fake_stdout = fake_stdout.getvalue()
      self.assertIn(f"Cannot overwrite portfolio at {path_db}", fake_stdout)
      self.assertNotEqual(rc, 0)

      # Overwrite
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, None, True, True)
      fake_stdout = fake_stdout.getvalue()
      self.assertEqual(fake_stdout, "")
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      path_db.unlink()

      # Create encrypted
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, path_password, False, False)
      fake_stdout = fake_stdout.getvalue()
      self.assertEqual(fake_stdout, "")
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      # Check password is correct
      portfolio.Portfolio(path_db, key)

      # Create encrypted
      queue = [key, key]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, path_password.with_suffix(".nonexistent"),
                             True, False)
      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password: \n"
                "Please confirm password: \n")
      self.assertEqual(fake_stdout, target)
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      # Check password is correct
      portfolio.Portfolio(path_db, key)

      # Create encrypted
      queue = [self.random_string(7), key, key + "typo", key, key]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, None, True, False)
      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password: \n"
                f"{Fore.RED}Password must be at least 8 characters\n"
                "Please enter password: \n"
                "Please confirm password: \n"
                f"{Fore.RED}Passwords must match\n"
                "Please enter password: \n"
                "Please confirm password: \n")
      self.assertEqual(fake_stdout, target)
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      # Check password is correct
      portfolio.Portfolio(path_db, key)

      # Cancel on first prompt
      queue = [None]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, None, True, False)
      fake_stdout = fake_stdout.getvalue()
      target = "Please enter password: \n"
      self.assertEqual(fake_stdout, target)
      self.assertNotEqual(rc, 0)

      # Cancel on second prompt
      queue = [key, None]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, None, True, False)
      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password: \n"
                "Please confirm password: \n")
      self.assertEqual(fake_stdout, target)
      self.assertNotEqual(rc, 0)

    finally:
      mock.builtins.input = original_input
      commands.common.getpass.getpass = original_get_pass

  def test_unlock(self):
    original_input = mock.builtins.input
    original_get_pass = commands.common.getpass.getpass

    queue: List[str] = []

    def mock_input(to_print: str):
      print(to_print)
      if len(queue) == 1:
        return queue[0]
      return queue.pop(0)

    try:
      mock.builtins.input = mock_input
      commands.common.getpass.getpass = mock_input

      path_db = self._TEST_ROOT.joinpath("portfolio.db")

      # Non-existent Portfolio
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, None)
      self.assertIsNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = (f"{Fore.RED}Portfolio does not exist at {path_db}. "
                "Run nummus create\n")
      self.assertEqual(target, fake_stdout)

      # Create and unlock unencrypted Portfolio
      commands.create(path_db, None, False, True)
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, None)
      self.assertIsNotNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = f"{Fore.GREEN}Portfolio is unlocked\n"
      self.assertEqual(target, fake_stdout)

      # Create and unlock encrypted Portfolio
      key = self.random_string()
      queue = [key, key]
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        commands.create(path_db, None, True, False)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(portfolio.Portfolio.is_encrypted(path_db),
                      "Portfolio is not encrypted")

      # Password file does not exist
      path_password = self._TEST_ROOT.joinpath(".password")
      self.assertFalse(path_password.exists(), "Password does exist")
      queue = [key]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, path_password)
      self.assertIsNotNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password: \n"
                f"{Fore.GREEN}Portfolio is unlocked\n")
      self.assertEqual(target, fake_stdout)

      # Password file does exist
      with open(path_password, "w", encoding="utf-8") as file:
        file.write(f"{key}\n")
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, path_password)
      self.assertIsNotNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = f"{Fore.GREEN}Portfolio is unlocked\n"
      self.assertEqual(target, fake_stdout)

      # Password file does exist but incorrect
      with open(path_password, "w", encoding="utf-8") as file:
        file.write(f"not the {key}\n")
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, path_password)
      self.assertIsNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = f"{Fore.RED}Could not decrypt with password file\n"
      self.assertEqual(target, fake_stdout)

      # No password file at all
      queue = [key]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, None)
      self.assertIsNotNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password: \n"
                f"{Fore.GREEN}Portfolio is unlocked\n")
      self.assertEqual(target, fake_stdout)

      # Cancel entry
      queue = [None]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, None)
      self.assertIsNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = "Please enter password: \n"
      self.assertEqual(target, fake_stdout)

      # 3 failed attempts
      queue = ["bad", "still wrong", "not going to work"]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        p = commands.unlock(path_db, None)
      self.assertIsNone(p)

      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password: \n"
                f"{Fore.RED}Incorrect password\n"
                "Please enter password: \n"
                f"{Fore.RED}Incorrect password\n"
                "Please enter password: \n"
                f"{Fore.RED}Incorrect password\n"
                f"{Fore.RED}Too many incorrect attempts\n")
      self.assertEqual(target, fake_stdout)

    finally:
      mock.builtins.input = original_input
      commands.common.getpass.getpass = original_get_pass
