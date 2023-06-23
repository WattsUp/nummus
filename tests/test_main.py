"""Test module nummus.main
"""

from typing import List, Dict

import functools
import io
import os
import pathlib
import subprocess
from unittest import mock

from nummus import main, commands, version

from tests.base import TestBase


class TestMain(TestBase):
  """Test main function
  """

  def _set_up_commands(self):
    """Set up mocked commands by replacing all commands with an argument logger
    """
    self._original_commands = {}
    for name in dir(commands):
      value = getattr(commands, name)
      if callable(value) and value.__module__.startswith("nummus"):
        self._original_commands[name] = value

    self._called_args: List[str] = []
    self._called_kwargs: Dict[str, object] = {}

    def check_call(*args, **kwargs):
      self._called_args.clear()
      self._called_args.extend(args)
      self._called_kwargs.clear()
      self._called_kwargs.update(kwargs)

    for name, value in self._original_commands.items():
      setattr(commands, name, functools.partial(check_call, _func=name))

  def _tear_down_commands(self):
    """Revert mocked commands
    """
    for name, value in self._original_commands.items():
      setattr(commands, name, value)

  def test_version(self):
    args = ["--version"]
    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      self.assertRaises(SystemExit, main, args)
    fake_stdout = fake_stdout.getvalue()
    self.assertEqual(fake_stdout, version.__version__ + "\n")

  def test_entrypoints(self):
    # Check can execute module
    process = subprocess.Popen("python3 -m nummus --version",
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               shell=True)
    stdout, stderr = process.communicate()
    stdout = stdout.decode().strip("\r\n").strip("\n")
    stderr = stderr.decode().strip("\r\n").strip("\n")
    self.assertEqual(stderr, "")
    self.assertEqual(stdout, version.__version__)

    # Check can execute entrypoint
    process = subprocess.Popen("nummus --version",
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               shell=True)
    stdout, stderr = process.communicate()
    stdout = stdout.decode().strip("\r\n").strip("\n")
    stderr = stderr.decode().strip("\r\n").strip("\n")
    self.assertEqual(stderr, "")
    self.assertEqual(stdout, version.__version__)

  def test_create(self):
    home = pathlib.Path(os.path.expanduser("~"))
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    path_password = str(self._TEST_ROOT.joinpath(".password"))
    try:
      self._set_up_commands()

      args = ["create"]
      main(args)
      self.assertListEqual(self._called_args, [])
      self.assertDictEqual(
          self._called_kwargs, {
              "_func": "create",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "force": False,
              "no_encrypt": False,
              "pass_file": None
          })

      args = ["create", "--no-encrypt"]
      main(args)
      self.assertListEqual(self._called_args, [])
      self.assertDictEqual(
          self._called_kwargs, {
              "_func": "create",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "force": False,
              "no_encrypt": True,
              "pass_file": None
          })

      args = [
          "--portfolio", path, "--pass-file", path_password, "create", "--force"
      ]
      main(args)
      self.assertListEqual(self._called_args, [])
      self.assertDictEqual(
          self._called_kwargs, {
              "_func": "create",
              "path": path,
              "force": True,
              "no_encrypt": False,
              "pass_file": path_password
          })
    finally:
      self._tear_down_commands()

  def test_unlock(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))

    # Try unlocking non-existent Portfolio
    args = ["--portfolio", path, "unlock"]
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      rc = main(args)
    self.assertNotEqual(rc, 0)

    commands.create(path, None, False, True)

    args = ["--portfolio", path, "unlock"]
    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      rc = main(args)
    self.assertEqual(rc, 0)

    fake_stdout = fake_stdout.getvalue()
    self.assertIn("Portfolio is unlocked", fake_stdout)

  def test_web(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    commands.create(path, None, False, True)

    args = ["--portfolio", path]
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      self.assertRaises(NotImplementedError, main, args)
    self.skipTest("Not implemented")

    home = pathlib.Path(os.path.expanduser("~"))
    path_password = str(self._TEST_ROOT.joinpath(".password"))
    try:
      self._set_up_commands()

      args = []
      main(args)
      self.assertListEqual(self._called_args, [])
      self.assertDictEqual(
          self._called_kwargs, {
              "_func": "web",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "pass_file": None
          })

      args = ["--portfolio", path, "--pass-file", path_password, "web"]
      main(args)
      self.assertListEqual(self._called_args, [])
      self.assertDictEqual(self._called_kwargs, {
          "_func": "web",
          "path": path,
          "pass_file": path_password
      })
    finally:
      self._tear_down_commands()
