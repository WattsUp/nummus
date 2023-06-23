"""Command line interface commands
"""

import pathlib

import colorama
from colorama import Fore

from nummus import common, portfolio

colorama.init(autoreset=True)


def create(path: str, force: bool, no_encrypt: bool, pass_file: str) -> int:
  """Create a new Portfolio

  Args:
    path: Path to Portfolio DB to create
    force: True will overwrite existing if necessary
    no_encrypt: True will not encrypt the Portfolio
    pass_file: Path to password file, None will prompt when necessary

  Returns:
    0 on success
    non-zero on failure
  """
  path_db = pathlib.Path(path)
  if path_db.exists():
    if force:
      path_db.unlink()
    else:
      print(f"{Fore.RED}Cannot overwrite portfolio at {path_db}. "
            "Try with --force")
      return 1

  key: str = None
  if not no_encrypt:
    if pass_file is not None:
      path_password = pathlib.Path(pass_file)
      if path_password.exists():
        with open(pass_file, "r", encoding="utf-8") as file:
          key = file.read().strip()

    # Get key from user is password file empty

    # Prompt user
    while key is None:
      key = common.get_input("Please enter password:", secure=True)
      if key is None:
        return 1

      if len(key) < 8:
        print(f"{Fore.RED}Password must be at least 8 characters")
        key = None
        continue

      repeat = common.get_input("Please confirm password:", secure=True)
      if repeat is None:
        return 1

      if key != repeat:
        print(f"{Fore.RED}Passwords must match")
        key = None

  portfolio.Portfolio.create(path_db, key)

  return 0
