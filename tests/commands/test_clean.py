from __future__ import annotations

import argparse
import io
from unittest import mock

from colorama import Fore

from nummus import portfolio
from nummus.commands import clean, create
from tests.base import TestBase


class TestClean(TestBase):
    def test_clean(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_backup_1 = path_db.with_suffix(".backup1.tar")
        path_backup_2 = path_db.with_suffix(".backup2.tar")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        p.backup()
        p.backup()

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertTrue(path_backup_2.exists(), "Backup #2 does not exist")

        size_before = path_db.stat().st_size

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = clean.Clean(path_db, None)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertEqual(rc, 0)
        size_after = path_db.stat().st_size
        p_change = size_before - size_after

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Portfolio cleaned\n"
            f"{Fore.CYAN}Portfolio was optimized by "
            f"{p_change / 1000:.1f}KB/{p_change / 1024:.1f}KiB\n"
        )
        self.assertEqual(fake_stdout, target)

        self.assertTrue(path_backup_1.exists(), "Backup #1 does not exist")
        self.assertFalse(path_backup_2.exists(), "Backup #2 does exist")

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

        cmd_class = clean.Clean
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
