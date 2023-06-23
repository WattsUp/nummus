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
        rc = commands.create(path_db, False, True, None)
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
        rc = commands.create(path_db, False, True, None)
      fake_stdout = fake_stdout.getvalue()
      self.assertIn(f"Cannot overwrite portfolio at {path_db}", fake_stdout)
      self.assertNotEqual(rc, 0)

      # Overwrite
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, True, True, None)
      fake_stdout = fake_stdout.getvalue()
      self.assertEqual(fake_stdout, "")
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      path_db.unlink()

      # Create encrypted
      queue = []
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, False, False, path_password)
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
        rc = commands.create(path_db, True, False,
                             path_password.with_suffix(".nonexistent"))
      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password:\n"
                "Please confirm password:\n")
      self.assertEqual(fake_stdout, target)
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      # Check password is correct
      portfolio.Portfolio(path_db, key)

      # Create encrypted
      queue = [self.random_string(7), key, key + "typo", key, key]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, True, False, None)
      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password:\n"
                f"{Fore.RED}Password must be at least 8 characters\n"
                "Please enter password:\n"
                "Please confirm password:\n"
                f"{Fore.RED}Passwords must match\n"
                "Please enter password:\n"
                "Please confirm password:\n")
      self.assertEqual(fake_stdout, target)
      self.assertEqual(rc, 0)
      self.assertTrue(path_db.exists(), "Portfolio does not exist")
      self.assertTrue(path_config.exists(), "Config does not exist")

      # Check password is correct
      portfolio.Portfolio(path_db, key)

      # Cancel on first prompt
      queue = [None]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, True, False, None)
      fake_stdout = fake_stdout.getvalue()
      target = "Please enter password:\n"
      self.assertEqual(fake_stdout, target)
      self.assertNotEqual(rc, 0)

      # Cancel on second prompt
      queue = [key, None]
      with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
        rc = commands.create(path_db, True, False, None)
      fake_stdout = fake_stdout.getvalue()
      target = ("Please enter password:\n"
                "Please confirm password:\n")
      self.assertEqual(fake_stdout, target)
      self.assertNotEqual(rc, 0)

    finally:
      mock.builtins.input = original_input
      commands.common.getpass.getpass = original_get_pass
