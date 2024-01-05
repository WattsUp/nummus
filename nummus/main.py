"""nummus main entry.

A personal financial information aggregator and planning tool. Collects and
categorizes transactions, manages budgets, tracks investments, calculates net
worth, and predicts future performance.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from nummus import custom_types as t
from nummus import version


def main(command_line: t.Strings | None = None) -> int:
    """Main program entry.

    Args:
        command_line: command line arguments, None for sys.argv

    Return:
        0 on success
        non-zero on failure
    """
    desc = """A personal financial information aggregator and planning tool.
Collects and categorizes transactions, manages budgets, tracks investments,
calculates net worth, and predicts future performance."""
    home = Path("~").expanduser()
    default_path = str(home.joinpath(".nummus", "portfolio.db"))
    parser = argparse.ArgumentParser(prog="nummus", description=desc)
    parser.add_argument("--version", action="version", version=version.__version__)
    parser.add_argument(
        "--portfolio",
        "-p",
        metavar="PATH",
        type=Path,
        default=default_path,
        help="specify portfolio.db location",
    )
    parser.add_argument(
        "--pass-file",
        metavar="PATH",
        type=Path,
        help="specify password file location, omit will prompt when necessary",
    )

    subparsers = parser.add_subparsers(dest="cmd", metavar="<command>", required=True)

    sub_create = subparsers.add_parser(
        "create",
        help="create nummus portfolio",
        description="Create a new nummus portfolio",
    )
    sub_create.add_argument(
        "--force",
        default=False,
        action="store_true",
        help="Force create a new portfolio, will overwrite existing",
    )
    sub_create.add_argument(
        "--no-encrypt",
        default=False,
        action="store_true",
        help="do not encrypt portfolio",
    )

    _ = subparsers.add_parser(
        "unlock",
        help="test unlocking portfolio",
        description="Test unlocking portfolio",
    )

    _ = subparsers.add_parser(
        "backup",
        help="backup portfolio",
        description="Backup portfolio to a tar.gz",
    )

    sub_restore = subparsers.add_parser(
        "restore",
        help="restore portfolio from backup",
        description="Restore portfolio from backup",
    )
    sub_restore.add_argument(
        "-v",
        metavar="VERSION",
        type=int,
        help="number of backup to use for restore, omit for latest",
    )
    sub_restore.add_argument(
        "-l",
        "--list",
        dest="list_ver",
        default=False,
        action="store_true",
        help="list available backups",
    )

    _ = subparsers.add_parser(
        "clean",
        help="clean portfolio folder",
        description="Delete unused portfolio files",
    )

    sub_import = subparsers.add_parser(
        "import",
        help="import files into portfolio",
        description="Import financial statements into portfolio",
    )
    sub_import.add_argument(
        "paths",
        metavar="PATH",
        type=Path,
        nargs="+",
        help="list of files and directories to import",
    )
    sub_import.add_argument(
        "--force",
        default=False,
        action="store_true",
        help="do not check for already imported files",
    )

    # TODO (WattsUp): Look for a home estimate API
    _ = subparsers.add_parser(
        "update-assets",
        help="update valuations for assets",
        description="Update asset valuations aka download market data for stocks",
    )

    sub_web = subparsers.add_parser(
        "web",
        help="start nummus web server",
        description="Default interface to nummus",
    )
    sub_web.add_argument(
        "--host",
        "-H",
        default="127.0.0.1",
        help="specify network address for web server",
    )
    sub_web.add_argument(
        "--port",
        "-P",
        default=8080,
        type=int,
        help="specify network port for web server",
    )
    sub_web.add_argument(
        "--debug",
        # Default to if it detects a dev install
        # Aka not at a clean tag on master branch
        default=(
            version.version_dict["branch"] != "master"
            or version.version_dict["distance"] != 0
            or version.version_dict["dirty"]
        ),
        action="store_true",
        help=argparse.SUPPRESS,
    )
    sub_web.add_argument(
        "--no-debug",
        dest="debug",
        action="store_false",
        help=argparse.SUPPRESS,
    )

    args = parser.parse_args(args=command_line)

    path_db: Path = args.portfolio
    path_password: Path = args.pass_file
    cmd: str = args.cmd

    # Defer import to make main loading faster
    from nummus import commands

    if cmd == "create":
        force: bool = args.force
        no_encrypt: bool = args.no_encrypt
        return commands.create(
            path_db=path_db,
            path_password=path_password,
            force=force,
            no_encrypt=no_encrypt,
        )
    if cmd == "restore":
        tar_ver: int = args.v
        list_ver: bool = args.list_ver
        return commands.restore(
            path_db=path_db,
            path_password=path_password,
            tar_ver=tar_ver,
            list_ver=list_ver,
        )

    p = commands.unlock(path_db=path_db, path_password=path_password)
    if p is None:
        return 1

    if cmd == "web":
        host: str = args.host
        port: int = args.port
        debug: bool = args.debug
        return commands.run_web(p, host=host, port=port, debug=debug)
    if cmd == "unlock":
        # Already unlocked
        return 0
    if cmd == "backup":
        return commands.backup(p)
    if cmd == "clean":
        return commands.clean(p)
    if cmd == "import":
        paths: t.Paths = args.paths
        force: bool = args.force
        return commands.import_files(p, paths=paths, force=force)
    if cmd == "update-assets":
        return commands.update_assets(p)
    else:  # noqa: RET505, pragma: no cover
        msg = f"Unknown command '{cmd}'"
        raise ValueError(msg)


if __name__ == "__main__":
    sys.exit(main())
