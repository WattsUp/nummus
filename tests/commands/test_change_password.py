from __future__ import annotations

import argparse
import io
from unittest import mock

from colorama import Fore

from nummus import portfolio
from nummus.commands import change_password, create
from nummus.models import Config, ConfigKey
from tests.base import TestBase


class MockPortfolio(portfolio.Portfolio):

    # Changing password takes a while so mock the actual function
    def change_key(self, key: str) -> None:
        print(f"Changing key to {key}")


class TestChangePassword(TestBase):
    def test_change_password(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        MockPortfolio.create(path_db, None)
        p = MockPortfolio(path_db, None)
        self.assertTrue(path_db.exists(), "Portfolio does not exist")

        with p.get_session() as s:
            expected_encrypted = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            self.assertIsNone(expected_encrypted)

        queue: list[str | None] = []

        def mock_input(to_print: str) -> str | None:
            print(to_print)
            if len(queue) == 0:
                return None
            return queue.pop(0)

        # Don't change either
        queue = []
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            c = change_password.ChangePassword(path_db, None)
            rc = c.run()
        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Portfolio is unlocked\n"
            "Change portfolio password? [y/N]: \n"
            f"{Fore.YELLOW}Neither password changing\n"
        )
        self.assertEqual(fake_stdout, target)
        self.assertEqual(rc, -1)

        # Cancel on portfolio key
        queue = ["y"]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            c = change_password.ChangePassword(path_db, None)
            rc = c.run()
        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Portfolio is unlocked\n"
            "Change portfolio password? [y/N]: \n"
            "Please enter password: \n"
        )
        self.assertEqual(fake_stdout, target)
        self.assertEqual(rc, -1)

        # Cancel on web key
        key = self.random_string()
        queue = ["y", key, key]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            c = change_password.ChangePassword(path_db, None)
            # Use MockPortfolio
            c._p = p  # noqa: SLF001
            rc = c.run()
        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Portfolio is unlocked\n"
            "Change portfolio password? [y/N]: \n"
            "Please enter password: \n"
            "Please confirm password: \n"
            "Change web password? [y/N]: \n"
            f"Changing key to {key}\n"
            f"{Fore.GREEN}Changed password(s)\n"
            f"{Fore.CYAN}Run 'nummus clean' to remove backups with old password\n"
        )
        self.assertEqual(fake_stdout, target)
        self.assertEqual(rc, 0)

        # Cancel on web key
        key = self.random_string()
        queue = ["y", key, key, "y"]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            c = change_password.ChangePassword(path_db, None)
            rc = c.run()
        fake_stdout = fake_stdout.getvalue()
        target = (
            f"{Fore.GREEN}Portfolio is unlocked\n"
            "Change portfolio password? [y/N]: \n"
            "Please enter password: \n"
            "Please confirm password: \n"
            "Change web password? [y/N]: \n"
            "Please enter password: \n"
        )
        self.assertEqual(fake_stdout, target)
        self.assertEqual(rc, -1)

        # Change portfolio to encrypted
        path_db.unlink()
        MockPortfolio.create(path_db, key)
        p = MockPortfolio(path_db, key)
        with p.get_session() as s:
            expected_encrypted = (
                s.query(Config.value).where(Config.key == ConfigKey.WEB_KEY).scalar()
            )
            if expected_encrypted is None:
                self.fail("WEB_KEY is missing")
            expected = p.decrypt_s(expected_encrypted)
            self.assertEqual(expected, key)

        # Cancel on web key
        web_key = self.random_string()
        queue = [key, "n", "y", web_key, web_key]
        with (
            mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout,
            mock.patch("builtins.input", new=mock_input) as _,
            mock.patch("getpass.getpass", new=mock_input) as _,
        ):
            c = change_password.ChangePassword(path_db, None)
            rc = c.run()
        fake_stdout = fake_stdout.getvalue()
        target = (
            "Please enter password: \n"
            f"{Fore.GREEN}Portfolio is unlocked\n"
            "Change portfolio password? [y/N]: \n"
            "Change web password? [y/N]: \n"
            "Please enter password: \n"
            "Please confirm password: \n"
            f"{Fore.GREEN}Changed password(s)\n"
            f"{Fore.CYAN}Run 'nummus clean' to remove backups with old password\n"
        )
        self.assertEqual(fake_stdout, target)
        self.assertEqual(rc, 0)

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

        cmd_class = change_password.ChangePassword
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
