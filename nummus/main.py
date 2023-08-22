"""nummus main entry

A personal financial information aggregator and planning tool. Collects and
categorizes transactions, manages budgets, tracks investments, calculates net
worth, and predicts future performance.
"""

import argparse
import os
import pathlib
import sys

from nummus import version
from nummus import custom_types as t


def main(command_line: t.Strings = None) -> int:
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
  home = pathlib.Path(os.path.expanduser("~")).resolve()
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
                                     required=True)

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
                          help="do not encrypt portfolio")

  _ = subparsers.add_parser("unlock",
                            help="test unlocking portfolio",
                            description="Test unlocking portfolio")

  _ = subparsers.add_parser("backup",
                            help="backup portfolio",
                            description="Backup portfolio to a tar.gz")

  sub_restore = subparsers.add_parser(
      "restore",
      help="restore portfolio from backup",
      description="Restore portfolio from backup")
  sub_restore.add_argument("-v",
                           metavar="VERSION",
                           type=int,
                           help="number of backup to use for restore, "
                           "omit for latest")

  _ = subparsers.add_parser("clean",
                            help="clean portfolio folder",
                            description="Delete unused portfolio files")

  sub_import = subparsers.add_parser(
      "import",
      help="import files into portfolio",
      description="Import financial statements into portfolio")
  sub_import.add_argument("paths",
                          metavar="PATH",
                          nargs="+",
                          help="list of files and directories to import")

  sub_web = subparsers.add_parser("web",
                                  help="start nummus web server",
                                  description="Default interface to nummus")
  sub_web.add_argument("--host",
                       "-H",
                       default="127.0.0.1",
                       help="specify network address for web server")
  sub_web.add_argument("--port",
                       "-P",
                       default=8080,
                       type=int,
                       help="specify network port for web server")
  sub_web.add_argument(
      "--debug",
      # Default to if it detects a dev install
      # Aka at a tag on master branch
      default=(version.version_dict["branch"] != "master" and
               version.version_dict["distance"] != 0),
      action="store_true",
      help=argparse.SUPPRESS)
  sub_web.add_argument("--no-debug",
                       dest="debug",
                       action="store_false",
                       help=argparse.SUPPRESS)

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
  elif cmd == "restore":
    tar_ver: int = args.v
    return commands.restore(path=path_db,
                            pass_file=path_password,
                            tar_ver=tar_ver)

  p = commands.unlock(path=path_db, pass_file=path_password)
  if p is None:
    return 1

  if cmd == "web":
    host: str = args.host
    port: int = args.port
    debug: bool = args.debug
    return commands.run_web(p, host=host, port=port, debug=debug)
  elif cmd == "unlock":
    # Already unlocked
    return 0
  elif cmd == "backup":
    return commands.backup(p)
  elif cmd == "clean":
    return commands.clean(p)
  elif cmd == "import":
    paths: t.Strings = args.paths
    return commands.import_files(p, paths=paths)
  else:
    raise ValueError(f"Unknown command '{cmd}'")  # pragma: no cover


if __name__ == "__main__":
  sys.exit(main())
