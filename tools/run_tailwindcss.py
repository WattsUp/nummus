"""Run tailwindcss to generate distribution CSS file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import colorama
from colorama import Fore

import nummus

if TYPE_CHECKING:
    import io

colorama.init(autoreset=True)


def main() -> None:
    """Main program entry."""
    folder = Path(nummus.__file__).parent.resolve().joinpath("static")

    path_config = folder.joinpath("tailwind.config.js")
    path_in = folder.joinpath("src", "main.css")
    path_out = folder.joinpath("dist", "main.css")

    args = [
        "tailwindcss",
        "-c",
        str(path_config),
        "-i",
        str(path_in),
        "-o",
        str(path_out),
        "--minify",
    ]
    args.extend(sys.argv[1:])
    with subprocess.Popen(
        args,  # noqa: S603
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    ) as p:
        stdout: io.BytesIO = p.stdout  # type: ignore[attr-defined]
        try:
            buf = ""
            while p.poll() is None:
                # Use read1() instead of read() or Popen.communicate() as both blocks
                # until EOF
                buf = buf + stdout.read1().decode()
                lines = buf.split("\n")
                if len(lines) == 0:
                    continue
                buf = lines[-1]
                lines.pop(-1)

                for line in lines:
                    if line.startswith("Rebuilding"):
                        print(f"{Fore.CYAN}{line}", flush=True)
                    elif line.startswith("Done"):
                        print(f"{Fore.GREEN}{line}", flush=True)
                    elif line.startswith("SyntaxError"):
                        print(f"{Fore.RED}{line}", flush=True)
                    else:
                        print(line, flush=True)
        except KeyboardInterrupt:
            print()  # Extra newline for after ^C


if __name__ == "__main__":
    sys.exit(main())
