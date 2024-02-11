"""Import statements and similar files into portfolio."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from colorama import Fore
from typing_extensions import override

from nummus import exceptions as exc
from nummus import portfolio
from nummus.commands.base import Base

if TYPE_CHECKING:
    import argparse


# TODO (WattsUp): Look for a home estimate API
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
        *_,
        force: bool = False,
    ) -> None:
        """Initize import command.

        Args:
            path_db: Path to Portfolio DB
            path_password: Path to password file, None will prompt when necessary
            paths: List of files or directories to import
            force: True will not check for already imported files
        """
        super().__init__(path_db, path_password)
        self._paths = paths
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
        if self._p is None:
            return 1
        # Back up Portfolio
        _, tar_ver = self._p.backup()
        success = False

        count = 0

        try:
            for path in self._paths:
                if not path.exists():
                    print(f"{Fore.RED}File does not exist: {path}")
                    return -1
                if path.is_dir():
                    for f in path.iterdir():
                        if f.is_file():
                            self._p.import_file(f, force=self._force)
                            count += 1
                else:
                    self._p.import_file(path, force=self._force)
                    count += 1

            success = True
        except exc.FileAlreadyImportedError as e:
            print(f"{Fore.RED}{e}")
            print(
                f"{Fore.YELLOW}Delete file or run import with --force flag which "
                "may create duplicate transactions.",
            )
            return -2
        except exc.UnknownImporterError as e:
            print(f"{Fore.RED}{e}")
            print(f"{Fore.YELLOW}Create a custom importer in {self._p.importers_path}")
            return -3
        finally:
            # Restore backup if anything went wrong
            # Coverage gets confused with finally blocks
            if not success:  # pragma: no cover
                portfolio.Portfolio.restore(self._p, tar_ver=tar_ver)
                print(f"{Fore.RED}Abandoned import, restored from backup")
        print(f"{Fore.GREEN}Imported {count} files")
        return 0
