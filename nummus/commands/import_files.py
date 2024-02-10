"""Import statements and similar files into portfolio."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus import exceptions as exc
from nummus import portfolio

if TYPE_CHECKING:
    from pathlib import Path


def import_files(
    p: portfolio.Portfolio,
    paths: list[Path],
    *_,
    force: bool = False,
) -> int:
    """Import a list of files or directories into a portfolio.

    Args:
        p: Working Portfolio
        paths: List of files or directories to import
        force: True will not check for already imported files

    Returns:
        0 on success
        non-zero on failure
    """
    # Back up Portfolio
    _, tar_ver = p.backup()
    success = False

    count = 0

    try:
        for path in paths:
            if not path.exists():
                print(f"{Fore.RED}File does not exist: {path}")
                return -1
            if path.is_dir():
                for f in path.iterdir():
                    if f.is_file():
                        p.import_file(f, force=force)
                        count += 1
            else:
                p.import_file(path, force=force)
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
        print(f"{Fore.YELLOW}Create a custom importer in {p.importers_path}")
        return -3
    finally:
        # Restore backup if anything went wrong
        # Coverage gets confused with finally blocks
        if not success:  # pragma: no cover
            portfolio.Portfolio.restore(p, tar_ver=tar_ver)
            print(f"{Fore.RED}Abandoned import, restored from backup")
    print(f"{Fore.GREEN}Imported {count} files")
    return 0
