"""Run yapf formatter and trim whitespace on all files
"""

import pathlib
import subprocess
import sys

import colorama
from colorama import Fore

colorama.init(autoreset=True)


def main() -> None:
  """Main program entry
  """

  cwd = pathlib.Path(__file__).parent.parent

  # Get a list of files
  files = list(cwd.rglob("**/*.py"))

  # Run yapf first
  args = ([
      "yapf",
      "-p",  # Run in parallel
      "-m",  # Print modified
      "-r",  # Recursive directories
      "-i",  # Edit in place
      # "-vv",  # Print file names when processing
  ] + files)
  stdout = subprocess.check_output(args, cwd=cwd).decode()
  for line in stdout.splitlines():
    if line.startswith("Reformatting"):
      print(f"{Fore.CYAN}{line}")
    elif line.startswith("Formatted"):
      print(f"{Fore.GREEN}{line}")
    else:
      print(line)

  # Trim trailing whitespace
  for f in files:
    with open(f, "r", encoding="utf-8") as file:
      buf = file.read()

    lines = [l.rstrip(" ") for l in buf.splitlines()]
    buf_trimmed = "\n".join(lines)
    # Add trailing newline to non-blank files
    if buf_trimmed != "":
      buf_trimmed += "\n"
    if buf == buf_trimmed:
      continue
    with open(f, "w", encoding="utf-8") as file:
      file.write(buf_trimmed)
    print(f"{Fore.GREEN}Trimmed {f}")


if __name__ == "__main__":
  sys.exit(main())
