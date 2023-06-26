"""Command line interface commands
"""

from typing import List

import pathlib

import colorama
from colorama import Fore

from nummus import common, portfolio

colorama.init(autoreset=True)


def create(path: str, pass_file: str, force: bool, no_encrypt: bool) -> int:
  """Create a new Portfolio

  Args:
    path: Path to Portfolio DB to create
    pass_file: Path to password file, None will prompt when necessary
    force: True will overwrite existing if necessary
    no_encrypt: True will not encrypt the Portfolio

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
      key = common.get_input("Please enter password: ", secure=True)
      if key is None:
        return 1

      if len(key) < 8:
        print(f"{Fore.RED}Password must be at least 8 characters")
        key = None
        continue

      repeat = common.get_input("Please confirm password: ", secure=True)
      if repeat is None:
        return 1

      if key != repeat:
        print(f"{Fore.RED}Passwords must match")
        key = None

  portfolio.Portfolio.create(path_db, key)

  return 0


def unlock(path: str, pass_file: str) -> portfolio.Portfolio:
  """Unlock an existing Portfolio

  Args:
    path: Path to Portfolio DB to create
    pass_file: Path to password file, None will prompt when necessary

  Returns:
    Unlocked Portfolio or None if unlocking failed
  """
  path_db = pathlib.Path(path)
  if not path_db.exists():
    print(f"{Fore.RED}Portfolio does not exist at {path_db}. Run nummus create")
    return None

  if not portfolio.Portfolio.is_encrypted(path_db):
    p = portfolio.Portfolio(path_db, None)
    print(f"{Fore.GREEN}Portfolio is unlocked")
    return p

  key: str = None

  if pass_file is not None:
    path_password = pathlib.Path(pass_file)
    if path_password.exists():
      with open(pass_file, "r", encoding="utf-8") as file:
        key = file.read().strip()

  if key is not None:
    # Try once with password file
    try:
      p = portfolio.Portfolio(path_db, key)
      print(f"{Fore.GREEN}Portfolio is unlocked")
      return p
    except TypeError:
      print(f"{Fore.RED}Could not decrypt with password file")
      return None

  # 3 attempts
  for _ in range(3):
    key = common.get_input("Please enter password: ", secure=True)
    if key is None:
      return None
    try:
      p = portfolio.Portfolio(path_db, key)
      print(f"{Fore.GREEN}Portfolio is unlocked")
      return p
    except TypeError:
      print(f"{Fore.RED}Incorrect password")
      # Try again

  print(f"{Fore.RED}Too many incorrect attempts")
  return None


def import_files(p: portfolio.Portfolio, paths: List[str]) -> int:
  """Import a list of files or directories into a portfolio

  Args:
    p: Working Portfolio
    paths: List of files or directories to import
  
  Returns:
    0 on success
    non-zero on failure
  """
  # Back up Portfolio
  p.backup()
  success = False

  count = 0

  try:
    for path in paths:
      file = pathlib.Path(path)
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
      p.restore()
      print(f"{Fore.RED}Abandoned import, restored from backup")
  print(f"{Fore.GREEN}Imported {count} files")
  return 0


def run_web(p: portfolio.Portfolio, host: str, port: int) -> int:
  """Run web server serving the nummus Portfolio

  Args:
    p: Working Portfolio
    host: IP to bind to
    port: Network port to bind to
  
  Returns:
    0 on success
    non-zero on failure
  """
  raise NotImplementedError