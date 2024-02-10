"""Run health checks for data validation."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from colorama import Fore

from nummus import health_checks
from nummus.models import HealthCheckIssue

if TYPE_CHECKING:
    from nummus import portfolio


def health_check(
    p: portfolio.Portfolio,
    limit: int = 10,
    ignores: list[str] | None = None,
    *_,
    always_descriptions: bool = False,
    no_ignores: bool = False,
    clear_ignores: bool = False,
) -> int:
    """Run a comprehensive health check looking for import errors.

    Args:
        p: Working Portfolio
        limit: Print first n issues for each check
        ignores: List of issue URIs to ignore
        always_descriptions: True will print every check's description,
            False will only print on failure
        no_ignores: True will print issues that have been ignored
        clear_ignores: True will unignore all issues

    Returns:
        0 on success
        non-zero on failure
    """
    with p.get_session() as s:
        if clear_ignores:
            s.query(HealthCheckIssue).delete()
        elif ignores:
            # Set ignore for all specified issues
            ids = {HealthCheckIssue.uri_to_id(uri) for uri in ignores}
            s.query(HealthCheckIssue).where(HealthCheckIssue.id_.in_(ids)).update(
                {HealthCheckIssue.ignore: True},
            )
        s.commit()

    limit = max(1, limit)
    any_issues = False
    any_severe_issues = False
    first_uri: str | None = None
    for check_type in health_checks.CHECKS:
        c = check_type(p, no_ignores=no_ignores)
        c.test()
        n_issues = len(c.issues)
        if n_issues == 0:
            print(f"{Fore.GREEN}Check '{c.name}' has no issues")
            if always_descriptions:
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
                f"{Fore.MAGENTA}  And {n_issues - limit} more issues, use --limit flag"
                " to see more",
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
