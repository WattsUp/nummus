from __future__ import annotations

import argparse
import io
from unittest import mock

from colorama import Fore

from nummus.commands import create, unlock
from tests.base import TestBase


class TestUnlock(TestBase):
    def test_unlock_unencrypted(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        # Create and unlock unencrypted Portfolio
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            c = unlock.Unlock(path_db, None)
            c.run()

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio is unlocked\n"
        self.assertEqual(fake_stdout, target)

    def test_args(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(
            dest="cmd",
            metavar="<command>",
            required=True,
        )

        cmd_class = unlock.Unlock
        sub = subparsers.add_parser(
            cmd_class.NAME,
            help=cmd_class.HELP,
            description=cmd_class.DESCRIPTION,
        )
        cmd_class.setup_args(sub)

        command_line = [cmd_class.NAME]
        args = parser.parse_args(args=command_line)
        args_d = vars(args)
        args_d["path_db"] = path_db
        args_d["path_password"] = None
        cmd: str = args_d.pop("cmd")
        self.assertEqual(cmd, cmd_class.NAME)

        # Make sure all args from parse_args are given to constructor
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            cmd_class(**args_d)
