"""Run formatters and trim whitespace on all files."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import colorama
from colorama import Fore

colorama.init(autoreset=True)


def main() -> None:
    """Main program entry."""
    check = "--check" in sys.argv

    cwd = Path(__file__).parent.parent

    # Sort imports with isort
    args = ["isort", "-j", "-1", "."]
    if check:
        args.append("--check")
    stdout = subprocess.check_output(args, cwd=cwd).decode()  # noqa: S603
    for line in stdout.splitlines():
        print(line)

    # Format with black
    args = ["black", "-W", "4", "."]
    if check:
        args.append("--check")
    stdout = subprocess.check_output(args, cwd=cwd).decode()  # noqa: S603
    for line in stdout.splitlines():
        print(line)

    # Get a list of files
    files: list[Path] = []
    folders = ["nummus", "tests", "tools"]
    for folder in folders:
        path = cwd.joinpath(folder)
        if not path.is_dir():
            msg = f"{path} is not a folder"
            raise TypeError(msg)
        files.extend(path.rglob("**/*.py"))
    files = [f for f in files if "data" not in str(f)]

    # Normalize line endings
    for f in files:
        # Do binary to normalize line endings to LF
        with f.open("rb") as file:
            buf = file.read()

        lines = buf.splitlines()
        buf_trimmed = b"\n".join(lines)
        # Add trailing newline to non-blank files
        if buf_trimmed != b"":
            buf_trimmed += b"\n"
        if buf == buf_trimmed:
            continue
        if check:
            print(f"ERROR: {f} has improper line endings")
            continue
        with f.open("wb") as file:
            file.write(buf_trimmed)
        print(f"{Fore.GREEN}Normalized {f} line endings")


if __name__ == "__main__":
    sys.exit(main())
