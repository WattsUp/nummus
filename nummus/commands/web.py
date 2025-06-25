"""Run web server for GUI."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from nummus.commands.base import BaseCommand

if TYPE_CHECKING:
    import argparse
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
        production: bool,
    ) -> None:
        """Initize clean command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            host: IP to bind to
            port: Network port to bind to
            production: True will use production web server
        """
        super().__init__(path_db, path_password)
        self._host = host
        self._port = port
        self._production = production

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
            "--production",
            default=False,
            action="store_true",
            help="run using production server",
        )

    @override
    def run(self) -> int:
        if self._p is None:
            return 1

        # Defer for faster time to main
        if self._production:
            raise NotImplementedError
        from nummus.web.server_debug import Server  # noqa: PLC0415

        s = Server(self._p, self._host, self._port)
        s.run()
        return 0
