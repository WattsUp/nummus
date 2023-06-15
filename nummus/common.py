"""Miscellaneous functions and classes
"""

import enum
import getpass
import random
import string
import sys


class RC(enum.Enum):
  """Command line return codes enumeration
  """

  SUCCESS = 0
  EXCEPTION = 1


def random_string(min_length: int = 8, max_length: int = 12) -> str:
  """Generate a random string with letter, numbers, and symbols

  Args:
    min_length: minimum length of string
    max_length: maximum length of string

  Returns:
    str Random length string with random characters
  """
  all_char = string.ascii_letters + string.punctuation + string.digits
  return "".join(
      random.choice(all_char)
      for _ in range(random.randint(min_length, max_length)))


def get_input(prompt: str = "",
              secure: bool = False,
              print_key: bool = None) -> str:
  """Get input from the user, optionally secure

  Args:
    prompt: string to print to user
    secure: True will prompt for a password
    print_key: True will print key symbol, False will not, None will check
      stdout.encoding

  Returns:
    str String entered by user, None if canceled
  """
  try:
    if secure:
      if print_key or (print_key is None and sys.stdout.encoding and
                       sys.stdout.encoding.lower().startswith("utf-")):
        input_ = getpass.getpass("\u26BF  " + prompt)
      else:
        input_ = getpass.getpass(prompt)
    else:
      input_ = input(prompt)
  except (KeyboardInterrupt, EOFError):
    return None
  return input_


def confirm(prompt: str = None, default=False) -> bool:
  """Prompt user for yes/no confirmation

  Args:
    prompt: string to print to user
    default: default response if only [Enter] is pressed

  Returns:
    bool True for yes, False for no
  """
  if prompt is None:
    prompt = "Confirm"

  if default:
    prompt += " [Y/n]: "
  else:
    prompt += " [y/N]: "

  while True:
    input_ = input(prompt)
    if not input_:
      return default
    if input_ in ["Y", "y"]:
      return True
    if input_ in ["N", "n"]:
      return False
    print()
    print("Please enter y or n.")
    print()
