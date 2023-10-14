"""Test module nummus.main
"""

import functools
import io
import os
import pathlib
import subprocess
from unittest import mock

from nummus import main, commands, portfolio, version
from nummus import custom_types as t

from tests.base import TestBase


class TestMain(TestBase):
  """Test main function
  """

  def _set_up_commands(self):
    """Set up mocked commands by replacing all commands with an argument logger
    """
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

  def test_no_command(self):
    args = []
    with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
      self.assertRaises(SystemExit, main, args)
    fake_stderr = fake_stderr.getvalue()
    self.assertIn("the following arguments are required: <command>",
                  fake_stderr)

  def test_entrypoints(self):
    # Check can execute module
    with subprocess.Popen("python3 -m nummus --version",
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=True) as process:
      stdout, stderr = process.communicate()
      stdout = stdout.decode().strip("\r\n").strip("\n")
      stderr = stderr.decode().strip("\r\n").strip("\n")
      self.assertEqual(stderr, "")
      self.assertEqual(stdout, version.__version__)

    # Check can execute entrypoint
    with subprocess.Popen("nummus --version",
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          shell=True) as process:
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
      self.assertListEqual([], self._called_args)
      self.assertDictEqual(
          {
              "_func": "create",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "force": False,
              "no_encrypt": False,
              "pass_file": None
          }, self._called_kwargs)

      args = ["create", "--no-encrypt"]
      main(args)
      self.assertListEqual([], self._called_args)
      self.assertDictEqual(
          {
              "_func": "create",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "force": False,
              "no_encrypt": True,
              "pass_file": None
          }, self._called_kwargs)

      args = [
          "--portfolio", path, "--pass-file", path_password, "create", "--force"
      ]
      main(args)
      self.assertListEqual([], self._called_args)
      self.assertDictEqual(
          {
              "_func": "create",
              "path": path,
              "force": True,
              "no_encrypt": False,
              "pass_file": path_password
          }, self._called_kwargs)
    finally:
      self._tear_down_commands()

  def test_unlock(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))

    # Try unlocking non-existent Portfolio
    args = ["--portfolio", path, "unlock"]
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      rc = main(args)
    self.assertNotEqual(rc, 0)

    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      commands.create(path, None, False, True)

    args = ["--portfolio", path, "unlock"]
    with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
      rc = main(args)
    self.assertEqual(rc, 0)

    fake_stdout = fake_stdout.getvalue()
    self.assertIn("Portfolio is unlocked", fake_stdout)

  def test_import(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      commands.create(path, None, False, True)

    try:
      self._set_up_commands()

      args = ["--portfolio", path, "import"]
      with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
        self.assertRaises(SystemExit, main, args)
      fake_stderr = fake_stderr.getvalue()
      self.assertIn("arguments are required: PATH", fake_stderr)

      paths = ["transactions.csv"]
      args = ["--portfolio", path, "import"] + paths
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      self.assertDictEqual({
          "_func": "import_files",
          "paths": paths
      }, self._called_kwargs)

      paths = ["transactions.csv", "statement-dir"]
      args = ["--portfolio", path, "import"] + paths
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      self.assertDictEqual({
          "_func": "import_files",
          "paths": paths
      }, self._called_kwargs)

    finally:
      self._tear_down_commands()

  def test_web(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      commands.create(path, None, False, True)

    try:
      self._set_up_commands()

      args = ["--portfolio", path, "web"]
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      is_dev = (version.version_dict["branch"] != "master" and
                version.version_dict["distance"] != 0)
      self.assertDictEqual(
          {
              "_func": "run_web",
              "host": "127.0.0.1",
              "port": 8080,
              "debug": is_dev
          }, self._called_kwargs)

      args = ["--portfolio", path, "web", "--debug"]
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      self.assertDictEqual(
          {
              "_func": "run_web",
              "host": "127.0.0.1",
              "port": 8080,
              "debug": True
          }, self._called_kwargs)

      host = "0.0.0.0"
      port = 80
      args = [
          "--portfolio", path, "web", "-H", host, "-P",
          str(port), "--no-debug"
      ]
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      self.assertDictEqual(
          {
              "_func": "run_web",
              "host": host,
              "port": port,
              "debug": False
          }, self._called_kwargs)
    finally:
      self._tear_down_commands()

  def test_restore(self):
    home = pathlib.Path(os.path.expanduser("~"))
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    path_password = str(self._TEST_ROOT.joinpath(".password"))
    try:
      self._set_up_commands()

      args = ["restore"]
      main(args)
      self.assertListEqual([], self._called_args)
      self.assertDictEqual(
          {
              "_func": "restore",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "pass_file": None,
              "tar_ver": None
          }, self._called_kwargs)

      tar_ver = self._RNG.integers(1, 100)
      args = ["restore", "-v", str(tar_ver)]
      main(args)
      self.assertListEqual([], self._called_args)
      self.assertDictEqual(
          {
              "_func": "restore",
              "path": str(home.joinpath(".nummus", "portfolio.db")),
              "pass_file": None,
              "tar_ver": tar_ver
          }, self._called_kwargs)

      args = ["--portfolio", path, "--pass-file", path_password, "restore"]
      main(args)
      self.assertListEqual([], self._called_args)
      self.assertDictEqual(
          {
              "_func": "restore",
              "path": path,
              "pass_file": path_password,
              "tar_ver": None
          }, self._called_kwargs)
    finally:
      self._tear_down_commands()

  def test_backup(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      commands.create(path, None, False, True)

    try:
      self._set_up_commands()

      args = ["--portfolio", path, "backup"]
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      self.assertDictEqual({"_func": "backup"}, self._called_kwargs)
    finally:
      self._tear_down_commands()

  def test_clean(self):
    path = str(self._TEST_ROOT.joinpath("portfolio.db"))
    with mock.patch("sys.stdout", new=io.StringIO()) as _:
      commands.create(path, None, False, True)

    try:
      self._set_up_commands()

      args = ["--portfolio", path, "clean"]
      with mock.patch("sys.stdout", new=io.StringIO()) as _:
        main(args)
      self.assertEqual(1, len(self._called_args))
      self.assertIsInstance(self._called_args[0], portfolio.Portfolio)
      self.assertDictEqual({"_func": "clean"}, self._called_kwargs)
    finally:
      self._tear_down_commands()
