"""Run viztracer profiler on a web call
"""

import argparse
import os
import pathlib
import sys
import time
import warnings

import colorama
from colorama import Fore
import connexion
import flask
import flask.testing
import viztracer
import werkzeug

from nummus import commands, web
from nummus import custom_types as t

colorama.init(autoreset=True)


def main(command_line: t.Strings = None) -> int:
  """Main program entry

  Args:
    command_line: command line arguments, None for sys.argv

  Return:
    0 on success
    non-zero on failure
  """
  desc = "Run viztracer profiler on a web call, only supports GET"
  home = pathlib.Path(os.path.expanduser("~")).resolve()
  default_path = str(home.joinpath(".nummus", "portfolio.db"))
  parser = argparse.ArgumentParser(prog="nummus", description=desc)
  parser.add_argument("--portfolio",
                      "-p",
                      metavar="PATH",
                      default=default_path,
                      help="specify portfolio.db location")
  parser.add_argument("--pass-file",
                      metavar="PATH",
                      help="specify password file location, "
                      "omit will prompt when necessary")
  parser.add_argument("--output-file",
                      "-o",
                      metavar="PATH",
                      default="result.json",
                      help="output file path. End with .json or .html or .gz")
  parser.add_argument("--save-response",
                      "-s",
                      metavar="PATH",
                      help="specify output file location to save web response")
  parser.add_argument("url",
                      metavar="URL",
                      help="web URL to call. Use relative to server "
                      "such as /api/transactions?limit=500")

  args = parser.parse_args(args=command_line)

  path_db: str = args.portfolio
  path_password: str = args.pass_file
  path_response: str = args.save_response
  output_file: str = args.output_file
  url: str = args.url

  p = commands.unlock(path=path_db, pass_file=path_password)
  if p is None:
    return 1

  s = web.Server(p, "127.0.0.1", 8080, False)
  s_server = s._server  # pylint: disable=protected-access
  connexion_app: connexion.FlaskApp = s_server.application
  flask_app: flask.Flask = connexion_app.app
  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    client = flask_app.test_client()

  print(f"{Fore.CYAN}GET {url}")
  response: werkzeug.test.TestResponse = None
  try:
    with viztracer.VizTracer(output_file=output_file) as _:
      start = time.perf_counter()
      response = client.open(url, method="GET")
      duration = time.perf_counter() - start
    print(f"{Fore.CYAN}Reply took {duration:.6}s")

    if path_response is not None:
      with open(path_response, "wb") as file:
        file.write(response.get_data())

    if response.status_code == 200:
      print(f"{Fore.GREEN}Server replied with HTTP.200")
    else:
      print(response.get_data(as_text=True))
      print(f"{Fore.RED}Server replied with HTTP.{response.status_code}")
      return 1

  finally:
    if response is not None:
      response.close()
  return 0


if __name__ == "__main__":
  sys.exit(main())