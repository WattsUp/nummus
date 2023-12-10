"""Command line interface commands."""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import colorama
from colorama import Fore

from nummus import custom_types as t
from nummus import exceptions as exc
from nummus import portfolio, utils, web

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
            return 1

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
                return 1

            if len(key) < MIN_PASS_LEN:
                print(f"{Fore.RED}Password must be at least {MIN_PASS_LEN} characters")
                key = None
                continue

            repeat = utils.get_input("Please confirm password: ", secure=True)
            if repeat is None:
                return 1

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
        except TypeError:
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
        except TypeError:
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
        return 1
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
    p.clean()
    print(f"{Fore.GREEN}Portfolio cleaned")
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
                return 1
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
            f"{Fore.CYAN}Delete file or run import with --force flag which "
            "may create duplicate transactions.",
        )
        return 2
    except exc.UnknownImporterError as e:
        print(f"{Fore.RED}{e}")
        print(f"{Fore.CYAN}Create a custom importer in {p.importers_path}")
        return 3
    except (TypeError, KeyError) as e:
        print(f"{Fore.RED}{e}")
        return 1
    finally:
        # Restore backup if anything went wrong
        # Coverage gets confused with finally blocks
        if not success:  # pragma: no cover
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned import, restored from backup")
    print(f"{Fore.GREEN}Imported {count} files")
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
