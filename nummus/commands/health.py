"""Run health checks for data validation."""

from __future__ import annotations

import textwrap
from typing import override, TYPE_CHECKING

from colorama import Fore

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
    from pathlib import Path

    from nummus import health_checks


class Health(BaseCommand):
    """Health check portfolio."""

    NAME = "health"
    HELP = "run a health check"
    DESCRIPTION = "Comprehensive health check looking for import issues"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        limit: int,
        ignores: list[str] | None,
        *,
        always_descriptions: bool,
        no_ignores: bool,
        clear_ignores: bool,
        no_description_typos: bool,
    ) -> None:
        """Initialize health check command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            limit: Print first n issues for each check
            ignores: List of issue URIs to ignore
            always_descriptions: True will print every check's description,
                False will only print on failure
            no_ignores: True will print issues that have been ignored
            clear_ignores: True will unignore all issues
            no_description_typos: True will not check descriptions for typos

        """
        super().__init__(path_db, path_password)
        self._limit = limit
        self._ignores = ignores
        self._always_descriptions = always_descriptions
        self._no_ignores = no_ignores
        self._clear_ignores = clear_ignores
        self._no_description_typos = no_description_typos

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-d",
            "--desc",
            default=False,
            action="store_true",
            help="print description of checks always",
            dest="always_descriptions",
        )
        parser.add_argument(
            "-l",
            "--limit",
            default=10,
            type=int,
            help="print the first n issues for each check",
        )
        parser.add_argument(
            "--no-ignores",
            default=False,
            action="store_true",
            help="print issues that have been ignored",
        )
        parser.add_argument(
            "--clear-ignores",
            default=False,
            action="store_true",
            help="unignore all issues",
        )
        parser.add_argument(
            "--no-description-typos",
            default=False,
            action="store_true",
            help="do not check descriptions for typos",
        )
        parser.add_argument(
            "-i",
            "--ignore",
            nargs="*",
            metavar="ISSUE_URI",
            help="ignore an issue specified by its URI",
            dest="ignores",
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        import datetime

        from nummus import health_checks
        from nummus.models import Config, ConfigKey, HealthCheckIssue

        p = self._p

        with p.begin_session() as s:
            if self._clear_ignores:
                s.query(HealthCheckIssue).delete()
            elif self._ignores:
                # Set ignore for all specified issues
                ids = {HealthCheckIssue.uri_to_id(uri) for uri in self._ignores}
                s.query(HealthCheckIssue).where(HealthCheckIssue.id_.in_(ids)).update(
                    {HealthCheckIssue.ignore: True},
                )

        any_issues = False
        any_severe_issues = False
        first_uri: str | None = None
        for check_type in health_checks.CHECKS:
            r = self._test_check(check_type)
            if r:
                first_uri = first_uri or r
                any_issues = True
                any_severe_issues = check_type.is_severe() or any_severe_issues
        if any_issues:
            print(f"{Fore.MAGENTA}Use web interface to fix issues")
            print(
                f"{Fore.MAGENTA}Or silence false positives with: nummus health "
                f"--ignore {first_uri} ...",
            )

        # Update LAST_HEALTH_CHECK_TS
        utc_now = datetime.datetime.now(datetime.UTC)
        with p.begin_session() as s:
            c = (
                s.query(Config)
                .where(Config.key == ConfigKey.LAST_HEALTH_CHECK_TS)
                .one_or_none()
            )
            if c is None:
                c = Config(
                    key=ConfigKey.LAST_HEALTH_CHECK_TS,
                    value=utc_now.isoformat(),
                )
                s.add(c)
            else:
                c.value = utc_now.isoformat()
        if any_severe_issues:
            return -2
        if any_issues:
            return -1
        return 0

    def _test_check(self, check_type: type[health_checks.Base]) -> str | None:
        """Test a health check.

        Args:
            check_type: Type of check to test

        Returns:
            First URI of issues or None if no issues

        """
        limit = max(1, self._limit)
        c = check_type(
            no_ignores=self._no_ignores,
            no_description_typos=self._no_description_typos,
        )
        with self._p.begin_session() as s:
            c.test(s)
        n_issues = len(c.issues)
        if n_issues == 0:
            print(f"{Fore.GREEN}Check '{c.name()}' has no issues")
            if self._always_descriptions:
                print(f"{Fore.CYAN}{textwrap.indent(c.description(), '    ')}")
            return None
        color = Fore.RED if c.is_severe() else Fore.YELLOW

        print(f"{color}Check '{c.name()}'")
        print(f"{Fore.CYAN}{textwrap.indent(c.description(), '    ')}")
        print(f"{color}  Has the following issues:")
        first_uri = ""
        # coverage wants to see c.issues be empty but that is checked above
        for i, (uri, issue) in enumerate(c.issues.items()):  # pragma: no cover
            first_uri = first_uri or uri
            if i >= limit:
                break
            line = f"[{uri}] {issue}"
            print(textwrap.indent(line, "  "))

        if n_issues > limit:
            print(
                f"{Fore.MAGENTA}  And {n_issues - limit} more issues, "
                "use --limit flag to see more",
            )

        return first_uri
