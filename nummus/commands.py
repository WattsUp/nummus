"""Command line interface commands."""
from __future__ import annotations

from pathlib import Path

import colorama
from colorama import Fore

from nummus import custom_types as t
from nummus import portfolio, utils, web

colorama.init(autoreset=True)

MIN_PASS_LEN = 8


def create(path: str, pass_file: str, *, force: bool, no_encrypt: bool) -> int:
    """Create a new Portfolio.

    Args:
        path: Path to Portfolio DB to create
        pass_file: Path to password file, None will prompt when necessary
        force: True will overwrite existing if necessary
        no_encrypt: True will not encrypt the Portfolio

    Returns:
        0 on success
        non-zero on failure
    """
    path_db = Path(path)
    if path_db.exists():
        if force:
            path_db.unlink()
        else:
            print(
                f"{Fore.RED}Cannot overwrite portfolio at {path_db}. Try with --force",
            )
            return 1

    key: str = None
    if not no_encrypt:
        if pass_file is not None:
            path_password = Path(pass_file)
            if path_password.exists():
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


def unlock(path: str, pass_file: str) -> portfolio.Portfolio:
    """Unlock an existing Portfolio.

    Args:
        path: Path to Portfolio DB to create
        pass_file: Path to password file, None will prompt when necessary

    Returns:
        Unlocked Portfolio or None if unlocking failed
    """
    path_db = Path(path)
    if not path_db.exists():
        print(f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create")
        return None

    if not portfolio.Portfolio.is_encrypted(path_db):
        p = portfolio.Portfolio(path_db, None)
        print(f"{Fore.GREEN}Portfolio is unlocked")
        return p

    key: str = None

    if pass_file is not None:
        path_password = Path(pass_file)
        if path_password.exists():
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


def restore(path: str, pass_file: str, tar_ver: t.Optional[int] = None) -> int:
    """Backup portfolio to tar.gz.

    Args:
        path: Path to Portfolio DB to restore
        pass_file: Path to password file, None will prompt when necessary
        tar_ver: Backup tar version to restore from, None will restore latest

    Returns:
        0 on success
        non-zero on failure
    """
    try:
        portfolio.Portfolio.restore(path, tar_ver=tar_ver)
        print(f"{Fore.CYAN}Extracted backup tar.gz")
    except FileNotFoundError as e:
        print(f"{Fore.RED}{e}")
        return 1
    p = unlock(path, pass_file)
    print(f"{Fore.GREEN}Portfolio restored for {p.path}")
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


def import_files(p: portfolio.Portfolio, paths: t.Strings) -> int:
    """Import a list of files or directories into a portfolio.

    Args:
        p: Working Portfolio
        paths: List of files or directories to import

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
            file = Path(path)
            if not file.exists():
                print(f"{Fore.RED}File does not exist: {file}")
                return 1
            if file.is_dir():
                for f in file.iterdir():
                    if f.is_file():
                        p.import_file(f)
                        count += 1
            else:
                p.import_file(file)
                count += 1

        success = True
    except TypeError as e:
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
