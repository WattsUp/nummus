"""Run health checks for data validation."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus import health_checks
from nummus.commands.base import Base
from nummus.models import HealthCheckIssue

if TYPE_CHECKING:
    import argparse
    from pathlib import Path


class Health(Base):
    """Health check portfolio."""

    NAME = "health"
    HELP = "run a health check"
    DESCRIPTION = "Comprehensive health check looking for import issues"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        limit: int = 10,
        ignores: list[str] | None = None,
        *_,
        always_descriptions: bool = False,
        no_ignores: bool = False,
        clear_ignores: bool = False,
    ) -> None:
        """Initize health check command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            limit: Print first n issues for each check
            ignores: List of issue URIs to ignore
            always_descriptions: True will print every check's description,
                False will only print on failure
            no_ignores: True will print issues that have been ignored
            clear_ignores: True will unignore all issues
        """
        super().__init__(path_db, path_password)
        self._limit = limit
        self._ignores = ignores
        self._always_descriptions = always_descriptions
        self._no_ignores = no_ignores
        self._clear_ignores = clear_ignores

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "-d",
            "--desc",
            default=False,
            action="store_true",
            help="print description of checks always",
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
            "-i",
            "--ignore",
            nargs="*",
            metavar="ISSUE_URI",
            help="ignore an issue specified by its URI",
        )

    @override
    def run(self) -> int:
        if self._p is None:
            return 1
        with self._p.get_session() as s:
            if self._clear_ignores:
                s.query(HealthCheckIssue).delete()
            elif self._ignores:
                # Set ignore for all specified issues
                ids = {HealthCheckIssue.uri_to_id(uri) for uri in self._ignores}
                s.query(HealthCheckIssue).where(HealthCheckIssue.id_.in_(ids)).update(
                    {HealthCheckIssue.ignore: True},
                )
            s.commit()

        limit = max(1, self._limit)
        any_issues = False
        any_severe_issues = False
        first_uri: str | None = None
        for check_type in health_checks.CHECKS:
            c = check_type(self._p, no_ignores=self._no_ignores)
            c.test()
            n_issues = len(c.issues)
            if n_issues == 0:
                print(f"{Fore.GREEN}Check '{c.name}' has no issues")
                if self._always_descriptions:
                    print(f"{Fore.CYAN}{textwrap.indent(c.description, '    ')}")
                continue
            any_issues = True
            any_severe_issues = c.is_severe or any_severe_issues
            color = Fore.RED if c.is_severe else Fore.YELLOW

            print(f"{color}Check '{c.name}'")
            print(f"{Fore.CYAN}{textwrap.indent(c.description, '    ')}")
            print(f"{color}  Has the following issues:")
            for i, (uri, issue) in enumerate(c.issues.items()):
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
        if any_issues:
            print(f"{Fore.MAGENTA}Use web interface to fix issues")
            print(
                f"{Fore.MAGENTA}Or silence false positives with: nummus health "
                f"--ignore {first_uri} ...",
            )
        if any_severe_issues:
            return -2
        if any_issues:
            return -1
        return 0
