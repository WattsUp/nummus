from __future__ import annotations

import argparse
import io
from unittest import mock

from colorama import Fore
from typing_extensions import override

from nummus import health_checks, portfolio
from nummus.commands import create, health
from nummus.models import HealthCheckIssue
from tests.base import TestBase


class TestHealth(TestBase):
    def test_health(self) -> None:
        path_db = self._TEST_ROOT.joinpath("portfolio.db")
        with mock.patch("sys.stdout", new=io.StringIO()) as _:
            create.Create(path_db, None, force=False, no_encrypt=True).run()
        self.assertTrue(path_db.exists(), "Portfolio does not exist")
        p = portfolio.Portfolio(path_db, None)

        d = {}

        class MockCheck(health_checks.Base):
            _NAME = "Mock Check"
            _DESC = "This description spans\nTWO lines"
            _SEVERE = False

            @override
            def test(self) -> None:
                self._issues_raw = dict(d)
                self._commit_issues()

        original_checks = health_checks.CHECKS

        try:
            health_checks.CHECKS = [MockCheck]

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertEqual(rc, 0)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n"
            self.assertEqual(fake_stdout, target)

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None, always_descriptions=True)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertEqual(rc, 0)

            desc = f"{Fore.CYAN}    This description spans\n    TWO lines\n"
            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n{desc}"
            self.assertEqual(fake_stdout, target)

            d["0"] = "Missing important information\nincluding this"
            d["1"] = "Missing some info"

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None, limit=0)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertNotEqual(rc, 0)

            with p.get_session() as s:
                n = s.query(HealthCheckIssue).count()
                self.assertEqual(n, 2)

                c = s.query(HealthCheckIssue).where(HealthCheckIssue.value == "0").one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, False)

                uri_0 = c.uri

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.YELLOW}Check 'Mock Check'\n{desc}"
                f"{Fore.YELLOW}  Has the following issues:\n"
                f"  [{uri_0}] Missing important information\n  including this\n"
                f"{Fore.MAGENTA}  And 1 more issues, use --limit flag to see more\n"
                f"{Fore.MAGENTA}Use web interface to fix issues\n"
                f"{Fore.MAGENTA}Or silence false positives with: "
                f"nummus health --ignore {uri_0} ...\n"
            )
            self.assertEqual(fake_stdout, target)

            d.pop("1")

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None, ignores=[uri_0])
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertEqual(rc, 0)

            with p.get_session() as s:
                c = s.query(HealthCheckIssue).one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, True)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n"
            self.assertEqual(fake_stdout, target)

            MockCheck._SEVERE = True  # noqa: SLF001
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None, no_ignores=True)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertNotEqual(rc, 0)

            with p.get_session() as s:
                c = s.query(HealthCheckIssue).one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, True)

                uri = c.uri

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Check 'Mock Check'\n{desc}"
                f"{Fore.RED}  Has the following issues:\n"
                f"  [{uri}] Missing important information\n  including this\n"
                f"{Fore.MAGENTA}Use web interface to fix issues\n"
                f"{Fore.MAGENTA}Or silence false positives with: "
                f"nummus health --ignore {uri} ...\n"
            )
            self.assertEqual(fake_stdout, target)

            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None, clear_ignores=True)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertNotEqual(rc, 0)

            with p.get_session() as s:
                c = s.query(HealthCheckIssue).one()
                self.assertEqual(c.check, "Mock Check")
                self.assertEqual(c.value, "0")
                self.assertEqual(c.ignore, False)

                uri = c.uri

            fake_stdout = fake_stdout.getvalue()
            target = (
                f"{Fore.RED}Check 'Mock Check'\n{desc}"
                f"{Fore.RED}  Has the following issues:\n"
                f"  [{uri}] Missing important information\n  including this\n"
                f"{Fore.MAGENTA}Use web interface to fix issues\n"
                f"{Fore.MAGENTA}Or silence false positives with: "
                f"nummus health --ignore {uri} ...\n"
            )
            self.assertEqual(fake_stdout, target)

            # Solving the issue should get rid of the Ignore
            d.pop("0")
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                c = health.Health(path_db, None)
            with mock.patch("sys.stdout", new=io.StringIO()) as fake_stdout:
                rc = c.run()
            self.assertEqual(rc, 0)

            with p.get_session() as s:
                n = s.query(HealthCheckIssue).count()
                self.assertEqual(n, 0)

            fake_stdout = fake_stdout.getvalue()
            target = f"{Fore.GREEN}Check 'Mock Check' has no issues\n"
            self.assertEqual(fake_stdout, target)
        finally:
            health_checks.CHECKS = original_checks

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

        cmd_class = health.Health
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
