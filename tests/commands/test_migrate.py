from __future__ import annotations

import argparse
import io
import shutil
from typing import TYPE_CHECKING
from unittest import mock

from colorama import Fore

from nummus import migrations
from nummus.commands import create, migrate
from tests.base import TestBase

if TYPE_CHECKING:
    from nummus import portfolio


class MockMigrator(migrations.Migrator):

    _VERSION = "999.0.0"

    def migrate(self, p: portfolio.Portfolio) -> list[str]:
        _ = p
        return ["Comments encountered during migration"]


class TestMigrate(TestBase):
    def test_migrate(self) -> None:
        # Test an original portfolio can be migrated all the way
        path_original = self._DATA_ROOT.joinpath("old_versions/v0.1.16.db")
        path_db = self._TEST_ROOT.joinpath("portfolio.db")

        shutil.copyfile(path_original, path_db)

        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            c = migrate.Migrate(path_db, None)
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.CYAN}This transaction had multiple payees, only one allowed: "
            "1948-03-15 Savings, please validate\n"
            f"{Fore.GREEN}Portfolio migrated to v0.2.0\n"
            f"{Fore.GREEN}Portfolio model schemas updated\n"
        )
        self.assertEqual(fake_stdout, target)

        # Again doesn't hurt
        with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
            rc = c.run()
        self.assertEqual(rc, 0)

        fake_stdout = fake_stdout.getvalue()
        target = f"{Fore.GREEN}Portfolio does not need migration\n"
        self.assertEqual(fake_stdout, target)

        original_migrators = migrations.MIGRATORS
        try:
            migrations.MIGRATORS = [MockMigrator]

            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertEqual(rc, 0)

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.CYAN}Comments encountered during migration\n"
                f"{Fore.GREEN}Portfolio migrated to v999.0.0\n"
            )
            self.assertEqual(fake_stdout, target)

        finally:
            migrations.MIGRATORS = original_migrators

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

        cmd_class = migrate.Migrate
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
