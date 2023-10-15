"""Run viztracer profiler on a web call."""
from __future__ import annotations

import argparse
import io
import sys
import time
import warnings
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import colorama
import viztracer
from colorama import Fore

from nummus import commands
from nummus import custom_types as t
from nummus import web

if TYPE_CHECKING:
    import werkzeug

colorama.init(autoreset=True)


def main(command_line: t.Strings = None) -> int:
    """Main program entry.

    Args:
        command_line: command line arguments, None for sys.argv

    Return:
        0 on success
        non-zero on failure
    """
    desc = "Run viztracer profiler on a web call, only supports GET"
    home = Path("~").expanduser()
    default_path = str(home.joinpath(".nummus", "portfolio.db"))
    parser = argparse.ArgumentParser(prog="nummus", description=desc)
    parser.add_argument(
        "--portfolio",
        "-p",
        metavar="PATH",
        default=default_path,
        help="specify portfolio.db location",
        type=Path,
    )
    parser.add_argument(
        "--pass-file",
        metavar="PATH",
        help="specify password file location, omit will prompt when necessary",
        type=Path,
    )
    parser.add_argument(
        "--output-file",
        "-o",
        metavar="PATH",
        default="result.json",
        help="output file path. End with .json or .html or .gz",
        type=Path,
    )
    parser.add_argument(
        "--save-response",
        "-s",
        metavar="PATH",
        help="specify output file location to save web response",
        type=Path,
    )
    parser.add_argument(
        "--no-call-twice",
        default=False,
        action="store_true",
        help="default is to profile only the second of two "
        "requests, this flag will profile the first request",
    )
    parser.add_argument(
        "url",
        metavar="URL",
        help="web URL to call. Use relative to server "
        "such as /api/transactions?limit=500",
    )

    args = parser.parse_args(args=command_line)

    path_db: Path = args.portfolio
    path_password: Path = args.pass_file
    path_response: Path = args.save_response
    output_file: Path = args.output_file
    url: str = args.url
    no_call_twice: bool = args.no_call_twice

    p = commands.unlock(path=path_db, pass_file=path_password)
    if p is None:
        return 1

    s = web.Server(p, "127.0.0.1", 8080, debug=False)
    flask_app = s._app  # noqa: SLF001
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        client = flask_app.test_client()

    print(f"{Fore.CYAN}GET {url}")
    response: werkzeug.test.TestResponse = None
    try:
        if not no_call_twice:
            # Send one request, sqlalchemy with cache queries and such
            # More akin to real usage
            # Hide stdout from first call to no duplicate debugging print statements
            with mock.patch("sys.stdout", new=io.StringIO()) as _:
                with mock.patch("sys.stderr", new=io.StringIO()) as fake_stderr:
                    _ = client.open(url, method="GET")
            fake_stderr = fake_stderr.getvalue()
            if fake_stderr != "":
                print(fake_stderr, file=sys.stderr)
                return 1

        with viztracer.VizTracer(output_file=output_file) as _:
            start = time.perf_counter()
            response = client.open(url, method="GET")
            duration = time.perf_counter() - start
        print(f"{Fore.CYAN}Reply took {duration:.6}s")

        if path_response is not None:
            with path_response.open("wb") as file:
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
