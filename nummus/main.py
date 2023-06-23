"""nummus main entry

A personal financial information aggregator and planning tool. Collects and
categorizes transactions, manages budgets, tracks investments, calculates net
worth, and predicts future performance.
"""

from typing import List

import argparse
import os
import pathlib
import sys

from nummus import version


def main(command_line: List[str] = None) -> int:
  """Main program entry

  Args:
    command_line: command line arguments, None for sys.argv

  Return:
    0 on success
    non-zero on failure
  """
  desc = """A personal financial information aggregator and planning tool.
Collects and categorizes transactions, manages budgets, tracks investments,
calculates net worth, and predicts future performance."""
  home = pathlib.Path(os.path.expanduser("~"))
  default_path = str(home.joinpath(".nummus", "portfolio.db"))
  parser = argparse.ArgumentParser(prog="nummus", description=desc)
  parser.add_argument("--version",
                      action="version",
                      version=version.__version__)
  parser.add_argument("--portfolio",
                      "-p",
                      metavar="PATH",
                      default=default_path,
                      help="specify portfolio.db location")
  parser.add_argument("--pass-file",
                      metavar="PATH",
                      help="specify password file location, "
                      "omit will prompt when necessary")

  subparsers = parser.add_subparsers(dest="cmd",
                                     metavar="<command>",
                                     required=False)

  sub_create = subparsers.add_parser(
      "create",
      help="create nummus portfolio",
      description="Create a new nummus portfolio")
  sub_create.add_argument("--force",
                          default=False,
                          action="store_true",
                          help="Force create a new portfolio, "
                          "will overwrite existing")
  sub_create.add_argument("--no-encrypt",
                          default=False,
                          action="store_true",
                          help="Do not encrypt portfolio")

  _ = subparsers.add_parser("unlock",
                            help="test unlocking portfolio",
                            description="Test unlocking portfolio")

  # sub_web = subparsers.add_parser("web",
  #                                 help="start gleMon web",
  #                                 description="Default interface to gleMon")
  # sub_web.add_argument("--host",
  #                      "-H",
  #                      default="127.0.0.1",
  #                      help="specify network address for web server")
  # sub_web.add_argument("--port",
  #                      "-P",
  #                      default=80,
  #                      type=int,
  #                      help="specify network port for web server")

  args = parser.parse_args(args=command_line)

  path_db: str = args.portfolio
  path_password: str = args.pass_file
  cmd: str = args.cmd

  # Defer import to make main loading faster
  from nummus import commands  # pylint: disable=import-outside-toplevel

  if cmd == "create":
    force: bool = args.force
    no_encrypt: bool = args.no_encrypt
    return commands.create(path=path_db,
                           pass_file=path_password,
                           force=force,
                           no_encrypt=no_encrypt)

  p = commands.unlock(path=path_db, pass_file=path_password)
  if p is None:
    return 1

  if cmd == "web" or cmd is None:
    # if not args.no_web:
    #   w = web.Server(p)
    #   rc = w.run(host=args.host, port=args.port)
    raise NotImplementedError
  elif cmd == "unlock":
    # Already unlocked
    return 0
  else:
    raise ValueError(f"Unknown command '{cmd}'")  # pragma: no cover


if __name__ == "__main__":
  sys.exit(main())
