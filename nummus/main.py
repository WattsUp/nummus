"""nummus main entry.

A personal financial information aggregator and planning tool. Collects and
categorizes transactions, manages budgets, tracks investments, calculates net
worth, and predicts future performance.
"""

# PYTHON_ARGCOMPLETE_OK

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import argcomplete

from nummus import commands, version


def main(command_line: list[str] | None = None) -> int:
    """Execute main program.

    Args:
        command_line: command line arguments, None for sys.argv

    Returns:
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
        dest="path_db",
        metavar="PATH",
        type=Path,
        default=default_path,
        help="specify portfolio.db location",
    )
    parser.add_argument(
        "--pass-file",
        dest="path_password",
        metavar="PATH",
        type=Path,
        help="specify password file location, omit will prompt when necessary",
    )

    subparsers = parser.add_subparsers(dest="cmd", metavar="<command>", required=True)

    for cmd_class in commands.COMMANDS.values():
        sub = subparsers.add_parser(
            cmd_class.NAME,
            help=cmd_class.HELP,
            description=cmd_class.DESCRIPTION,
        )
        cmd_class.setup_args(sub)

    argcomplete.autocomplete(parser)
    args = parser.parse_args(args=command_line)

    args_d = vars(args)
    cmd: str = args_d.pop("cmd")
    c = commands.COMMANDS[cmd](**args_d)
    return c.run()


if __name__ == "__main__":
    sys.exit(main())
