"""Run tailwindcss to generate distribution CSS file
"""

import io
import pathlib
import subprocess
import sys

import colorama
from colorama import Fore

import nummus.web

colorama.init(autoreset=True)


def main() -> None:
  """Main program entry
  """

  path_web = pathlib.Path(nummus.web.__file__).parent.resolve()

  path_config = path_web.joinpath("static", "tailwind.config.js")
  path_in = path_web.joinpath("static", "src", "main.css")
  path_out = path_web.joinpath("static", "dist", "main.css")

  args = [
      "tailwindcss", "-c",
      str(path_config), "-i",
      str(path_in), "-o",
      str(path_out), "--minify"
  ]
  args.extend(sys.argv[1:])
  with subprocess.Popen(args, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT) as p:
    stdout: io.BytesIO = p.stdout
    try:
      buf = ""
      while p.poll() is None:
        # Use read1() instead of read() or Popen.communicate() as both blocks
        # until EOF
        buf = buf + stdout.read1().decode()
        lines = buf.split("\n")
        if len(lines) == 0:
          continue
        if lines[-1] == "":
          # Finishing with a \n will have an empty string in the end
          buf = ""
        else:
          # Last line is not finished
          buf = lines[-1]
        lines.pop(-1)

        for line in lines:
          if line.startswith("Rebuilding"):
            print(f"{Fore.CYAN}{line}", flush=True)
          elif line.startswith("Done"):
            print(f"{Fore.GREEN}{line}", flush=True)
          else:
            print(line, flush=True)
    except KeyboardInterrupt:
      print()  # Extra newline for after ^C


if __name__ == "__main__":
  sys.exit(main())
