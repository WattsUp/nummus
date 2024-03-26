from __future__ import annotations

import argparse
import io
from unittest import mock

from colorama import Fore

from nummus.commands import backup, create
from tests.base import TestBase


class TestBackUp(TestBase):
    def test_backup_restore(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        path_backup = path_db.with_suffix(".backup1.tar.gz")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            c = backup.Restore(path_db, None, list_ver=True, tar_ver=None)
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.RED}No backups found, run nummus backup"
        self.assertEqual(fake_stdout[: len(target)], target)

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = backup.Backup(path_db, None)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio backed up to {path_backup}\n"
        self.assertEqual(fake_stdout, target)

        self.assertTrue(path_backup.exists(), "Backup does not exist")

        path_db.unlink()
        self.assertFalse(path_db.exists(), "Portfolio does exist")

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            c = backup.Restore(path_db, None, list_ver=True, tar_ver=None)
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.CYAN}Backup # 1 created at"
        self.assertEqual(fake_stdout[: len(target)], target)

        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            c = backup.Restore(path_db, None, list_ver=False, tar_ver=None)
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.CYAN}Extracted backup tar.gz\n"
            f"{Fore.GREEN}Portfolio is unlocked\n"
            f"{Fore.GREEN}Portfolio restored for {path_db}\n"
        )
        self.assertEqual(fake_stdout, target)

        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        path_backup.unlink()
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            c = backup.Restore(path_db, None, list_ver=False, tar_ver=1)
            rc = c.run()
        self.assertNotEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.RED}Backup does not exist {path_backup}\n"
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

        cmd_class = backup.Backup
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

        cmd_class = backup.Restore
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
