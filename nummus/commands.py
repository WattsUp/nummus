"""Command line interface commands."""

from __future__ import annotations

import datetime
import textwrap
from typing import TYPE_CHECKING

import colorama
from colorama import Fore

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import health_checks, portfolio, utils, web
from nummus.models import HealthCheckIssue

if TYPE_CHECKING:
    from pathlib import Path

colorama.init(autoreset=True)

MIN_PASS_LEN = 8


def create(
    path_db: Path,
    path_password: Path | None,
    *,
    force: bool,
    no_encrypt: bool,
) -> int:
    """Create a new Portfolio.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary
        force: True will overwrite existing if necessary
        no_encrypt: True will not encrypt the Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    if path_db.exists():
        if force:
            path_db.unlink()
        else:
            print(
                f"{Fore.RED}Cannot overwrite portfolio at {path_db}. Try with --force",
            )
            return -1

    key: str | None = None
    if not no_encrypt:
        if path_password is not None and path_password.exists():
            with path_password.open(encoding="utf-8") as file:
                key = file.read().strip()

        # Get key from user is password file empty

        # Prompt user
        while key is None:
            key = utils.get_input("Please enter password: ", secure=True)
            if key is None:
                return -1

            if len(key) < MIN_PASS_LEN:
                print(f"{Fore.RED}Password must be at least {MIN_PASS_LEN} characters")
                key = None
                continue

            repeat = utils.get_input("Please confirm password: ", secure=True)
            if repeat is None:
                return -1

            if key != repeat:
                print(f"{Fore.RED}Passwords must match")
                key = None

    portfolio.Portfolio.create(path_db, key)
    print(f"{Fore.GREEN}Portfolio created at {path_db}")

    return 0


def unlock(path_db: Path, path_password: Path | None) -> portfolio.Portfolio | None:
    """Unlock an existing Portfolio.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary

    Returns:
        Unlocked Portfolio or None if unlocking failed
    """
    if not path_db.exists():
        print(f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create")
        return None

    if not portfolio.Portfolio.is_encrypted(path_db):
        p = portfolio.Portfolio(path_db, None)
        print(f"{Fore.GREEN}Portfolio is unlocked")
        return p

    key: str | None = None

    if path_password is not None and path_password.exists():
        with path_password.open(encoding="utf-8") as file:
            key = file.read().strip()

    if key is not None:
        # Try once with password file
        try:
            p = portfolio.Portfolio(path_db, key)
        except exc.UnlockingError:
            print(f"{Fore.RED}Could not decrypt with password file")
            return None
        else:
            print(f"{Fore.GREEN}Portfolio is unlocked")
            return p

    # 3 attempts
    for _ in range(3):
        key = utils.get_input("Please enter password: ", secure=True)
        if key is None:
            return None
        try:
            p = portfolio.Portfolio(path_db, key)
        except exc.UnlockingError:
            print(f"{Fore.RED}Incorrect password")
            # Try again
        else:
            print(f"{Fore.GREEN}Portfolio is unlocked")
            return p

    print(f"{Fore.RED}Too many incorrect attempts")
    return None


def backup(p: portfolio.Portfolio) -> int:
    """Backup portfolio to tar.gz.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    backup_tar, _ = p.backup()
    print(f"{Fore.GREEN}Portfolio backed up to {backup_tar}")
    return 0


def restore(
    path_db: Path,
    path_password: Path | None,
    tar_ver: int | None = None,
    *_,
    list_ver: bool = False,
) -> int:
    """Backup portfolio to tar.gz.

    Args:
        path_db: Path to Portfolio DB to create
        path_password: Path to password file, None will prompt when necessary
        tar_ver: Backup tar version to restore from, None will restore latest
        list_ver: True will list backups available, False will restore

    Returns:
        0 on success
        non-zero on failure
    """
    try:
        if list_ver:
            backups = portfolio.Portfolio.backups(path_db)
            if len(backups) == 0:
                print(f"{Fore.RED}No backups found, run nummus backup")
                return 0
            now = datetime.datetime.now(datetime.timezone.utc)
            for ver, ts in backups:
                ago_s = (now - ts).total_seconds()
                ago = utils.format_seconds(ago_s)

                # Convert ts utc to local timezone
                ts_local = ts.astimezone()
                print(
                    f"{Fore.CYAN}Backup #{ver:2} created at "
                    f"{ts_local.isoformat(timespec='seconds')} ({ago} ago)",
                )
            return 0
        portfolio.Portfolio.restore(path_db, tar_ver=tar_ver)
        print(f"{Fore.CYAN}Extracted backup tar.gz")
    except FileNotFoundError as e:
        print(f"{Fore.RED}{e}")
        return -1
    p = unlock(path_db, path_password)
    print(f"{Fore.GREEN}Portfolio restored for {p and p.path}")
    return 0


def clean(p: portfolio.Portfolio) -> int:
    """Clean portfolio and delete unused files.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    size_before, size_after = p.clean()
    print(f"{Fore.GREEN}Portfolio cleaned")
    p_change = size_before - size_after
    print(
        f"{Fore.CYAN}Portfolio was optimized by "
        f"{p_change / 1000:,.1f}KB/{p_change / 1024:,.1f}KiB",
    )

    return 0


def import_files(
    p: portfolio.Portfolio,
    paths: t.Paths,
    *_,
    force: bool = False,
) -> int:
    """Import a list of files or directories into a portfolio.

    Args:
        p: Working Portfolio
        paths: List of files or directories to import
        force: True will not check for already imported files

    Returns:
        0 on success
        non-zero on failure
    """
    # Back up Portfolio
    _, tar_ver = p.backup()
    success = False

    count = 0

    try:
        for path in paths:
            if not path.exists():
                print(f"{Fore.RED}File does not exist: {path}")
                return -1
            if path.is_dir():
                for f in path.iterdir():
                    if f.is_file():
                        p.import_file(f, force=force)
                        count += 1
            else:
                p.import_file(path, force=force)
                count += 1

        success = True
    except exc.FileAlreadyImportedError as e:
        print(f"{Fore.RED}{e}")
        print(
            f"{Fore.YELLOW}Delete file or run import with --force flag which "
            "may create duplicate transactions.",
        )
        return -2
    except exc.UnknownImporterError as e:
        print(f"{Fore.RED}{e}")
        print(f"{Fore.YELLOW}Create a custom importer in {p.importers_path}")
        return -3
    finally:
        # Restore backup if anything went wrong
        # Coverage gets confused with finally blocks
        if not success:  # pragma: no cover
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned import, restored from backup")
    print(f"{Fore.GREEN}Imported {count} files")
    return 0


def update_assets(p: portfolio.Portfolio) -> int:
    """Update asset valuations using web sources.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    # Back up Portfolio
    _, tar_ver = p.backup()
    success = False

    try:
        updated = p.update_assets()
        success = True
    finally:
        # Restore backup if anything went really wrong
        # Coverage gets confused with finally blocks
        if not success:  # pragma: no cover
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned update-assets, restored from backup")

    if len(updated) == 0:
        print(
            f"{Fore.YELLOW}No assets were updated, "
            "add a ticker to an Asset to download market data",
        )
        return -2

    updated = sorted(updated, key=lambda item: item[0].lower())  # sort by name
    name_len = max(len(item[0]) for item in updated)
    ticker_len = max(len(item[1]) for item in updated)
    failed = False
    for name, ticker, start, end, error in updated:
        if start is None:
            print(
                f"{Fore.RED}Asset {name:{name_len}} ({ticker:{ticker_len}}) "
                f"failed to update. Error: {error}",
            )
            failed = True
        else:
            print(
                f"{Fore.GREEN}Asset {name:{name_len}} ({ticker:{ticker_len}}) "
                f"updated from {start} to {end}",
            )
    return 1 if failed else 0


def summarize(p: portfolio.Portfolio) -> int:
    """Print summary information and statistics on Portfolio.

    Args:
        p: Working Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    stats = p.summarize()

    def is_are(i: int) -> str:
        return "is" if i == 1 else "are"

    def plural(i: int) -> str:
        return "" if i == 1 else "s"

    size: int = stats["db_size"]
    print(f"Portfolio file size is {size/1000:,.1f}KB/{size/1024:,.1f}KiB")

    # Accounts
    table: list[list[str] | None] = [
        [
            "Name",
            "Institution.",
            "Category",
            ">Value/",
            ">Profit/",
            "^Age/",
        ],
        None,
    ]
    table.extend(
        [
            acct["name"],
            acct["institution"],
            acct["category"],
            utils.format_financial(acct["value"]),
            utils.format_financial(acct["profit"]),
            acct["age"],
        ]
        for acct in stats["accounts"]
    )
    table.append(None)
    table.append(
        [
            "Total",
            "",
            "",
            utils.format_financial(stats["net_worth"]),
            "",
            "",
        ],
    )
    n = stats["n_accounts"]
    n_table = len(stats["accounts"])
    print(
        f"There {is_are(n)} {n:,} account{plural(n)}, "
        f"{n_table:,} of which {is_are(n_table)} currently open",
    )
    utils.print_table(table)

    # Assets
    table = [
        [
            "Name",
            "Description.",
            "Class",
            "Ticker",
            ">Value/",
            ">Profit/",
        ],
        None,
    ]
    table.extend(
        [
            asset["name"],
            asset["description"] or "",
            asset["category"],
            asset["ticker"] or "",
            utils.format_financial(asset["value"]),
            utils.format_financial(asset["profit"]),
        ]
        for asset in stats["assets"]
    )
    table.append(None)
    table.append(
        [
            "Total",
            "",
            "",
            "",
            utils.format_financial(stats["total_asset_value"]),
            "",
        ],
    )
    n = stats["n_assets"]
    n_table = len(stats["assets"])
    print(
        f"There {is_are(n)} {n:,} asset{plural(n)}, "
        f"{n_table:,} of which {is_are(n_table)} currently held",
    )
    utils.print_table(table)

    n = stats["n_valuations"]
    print(f"There {is_are(n)} {n:,} asset valuation{plural(n)}")

    n = stats["n_transactions"]
    print(f"There {is_are(n)} {n:,} transaction{plural(n)}")
    return 0


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
        # Remove any issues not ignored
        s.query(HealthCheckIssue).where(HealthCheckIssue.ignore.is_(False)).delete()
        s.commit()

    limit = max(1, limit)
    any_issues = False
    any_severe_issues = False
    first_uri: str | None = None
    for check_type in health_checks.CHECKS:
        c = check_type(no_ignores=no_ignores)
        c.test(p)
        c.commit_issues(p)
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
        i = 0
        for uri, issue in c.issues.items():
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
            f"{Fore.MAGENTA}Or silence false positives with: nummus health -i "
            f"{first_uri} ...",
        )
    if any_severe_issues:
        return -2
    if any_issues:
        return -1
    return 0


# No unit test for wrapper command, too difficult to mock
def run_web(
    p: portfolio.Portfolio,
    host: str,
    port: int,
    *,
    debug: bool,
) -> int:  # pragma: no cover
    """Run web server serving the nummus Portfolio.

    Args:
        p: Working Portfolio
        host: IP to bind to
        port: Network port to bind to
        debug: True will run Flask in debug mode

    Returns:
        0 on success
        non-zero on failure
    """
    s = web.Server(p, host, port, debug=debug)
    s.run()
    return 0
