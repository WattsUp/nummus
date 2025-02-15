"""Import statements and similar files into portfolio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus.commands.base import Base

if TYPE_CHECKING:
    import argparse


class Import(Base):
    """Import files into portfolio."""

    NAME = "import"
    HELP = "import files into portfolio"
    DESCRIPTION = "Import financial statements into portfolio"

    def __init__(
        self,
        path_db: Path,
        path_password: Path | None,
        paths: list[Path],
        *,
        force: bool,
    ) -> None:
        """Initize import command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            paths: List of files or directories to import
            force: True will not check for already imported files
        """
        super().__init__(path_db, path_password)
        self._paths = [path.expanduser() for path in paths]
        self._force = force

    @override
    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "paths",
            metavar="PATH",
            type=Path,
            nargs="+",
            help="list of files and directories to import",
        )
        parser.add_argument(
            "--force",
            default=False,
            action="store_true",
            help="do not check for already imported files",
        )

    @override
    def run(self) -> int:
        # Defer for faster time to main
        from nummus import exceptions as exc
        from nummus import portfolio

        p = self._p
        if p is None:  # pragma: no cover
            return 1
        # Back up Portfolio
        _, tar_ver = p.backup()

        count = 0

        path_debug = p.path.with_suffix(".importer_debug")

        def restore() -> None:
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned import, restored from backup")
            if path_debug.exists():
                print(f"{Fore.YELLOW}Raw imported file may help at {path_debug}")

        try:
            for path in self._paths:
                if not path.exists():
                    print(f"{Fore.RED}File does not exist: {path}")
                    return -1
                if path.is_dir():
                    for f in path.iterdir():
                        if f.is_file():
                            p.import_file(f, path_debug, force=self._force)
                            count += 1
                else:
                    p.import_file(path, path_debug, force=self._force)
                    count += 1
        except exc.FileAlreadyImportedError as e:
            print(f"{Fore.RED}{e}")
            print(
                f"{Fore.YELLOW}Delete file or run import with --force flag which "
                "may create duplicate transactions.",
            )
            restore()
            return -2
        except exc.UnknownImporterError as e:
            print(f"{Fore.RED}{e}")
            print(f"{Fore.YELLOW}Create a custom importer in {p.importers_path}")
            restore()
            return -3
        except Exception as e:
            restore()
            raise exc.FailedCommandError(self.NAME) from e
        print(f"{Fore.GREEN}Imported {count} files")
        return 0
