"""Run web server for GUI."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from typing_extensions import override

from nummus import version
from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    from pathlib import Path


# web is difficult to mock, and just a wrapper command
class Web(BaseCommand):  # pragma: no cover
    """Web server for nummus."""

    NAME = "web"
    HELP = "start nummus web server"
    DESCRIPTION = "Default interface to nummus"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        host: str,
        port: int,
        *,
        debug: bool,
    ) -> None:
        """Initize clean command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            host: IP to bind to
            port: Network port to bind to
            debug: True will run Flask in debug mode
        """
        super().__init__(path_db, path_password)
        self._host = host
        self._port = port
        self._debug = debug

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--host",
            "-H",
            default="127.0.0.1",
            help="specify network address for web server",
        )
        parser.add_argument(
            "--port",
            "-P",
            default=8080,
            type=int,
            help="specify network port for web server",
        )
        parser.add_argument(
            "--debug",
            # Default to if it detects a dev install
            # Aka not at a clean tag
            default=(len(version.version_tuple) > 3),  # noqa: PLR2004
            action="store_true",
            help=argparse.SUPPRESS,
        )
        parser.add_argument(
            "--no-debug",
            dest="debug",
            action="store_false",
            help=argparse.SUPPRESS,
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus import web

        if self._p is None:
            return 1
        s = web.Server(self._p, self._host, self._port, debug=self._debug)
        s.run()
        return 0
