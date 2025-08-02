from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from colorama import Fore

from nummus.commands.import_files import Import

if TYPE_CHECKING:
    import datetime
    from pathlib import Path

    from nummus.models import Account, Asset
    from nummus.portfolio import Portfolio


def test_empty(capsys: pytest.CaptureFixture, empty_portfolio: Portfolio) -> None:
    path_debug = empty_portfolio.path.with_suffix(".importer_debug")

    c = Import(empty_portfolio.path, None, [], force=False)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n{Fore.GREEN}Imported 0 files\n"
    assert captured.out == target
    assert not captured.err

    assert not path_debug.exists()


def test_non_existant(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    tmp_path: Path,
) -> None:
    path = tmp_path / "to import.csv"
    path_debug = empty_portfolio.path.with_suffix(".importer_debug")

    c = Import(empty_portfolio.path, None, [path], force=False)
    assert c.run() != 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    target = (
        f"{Fore.RED}File does not exist: {path}\n"
        f"{Fore.RED}Abandoned import, restored from backup\n"
    )
    assert captured.err == target

    assert not path_debug.exists()


def test_data_dir(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
    tmp_path: Path,
    data_path: Path,
) -> None:
    _ = account
    _ = account_investments
    _ = asset
    files = [
        "transactions_required.csv",
        "transactions_extras.csv",
    ]
    for f in files:
        shutil.copyfile(data_path / f, tmp_path / f)
    (tmp_path / "more").mkdir()
    path_debug = empty_portfolio.path.with_suffix(".importer_debug")

    c = Import(empty_portfolio.path, None, [tmp_path], force=False)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n{Fore.GREEN}Imported 2 files\n"
    assert captured.out == target
    assert not captured.err

    assert not path_debug.exists()


def test_unknown_importer(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
    tmp_path: Path,
    data_path: Path,
) -> None:
    _ = account
    _ = account_investments
    _ = asset
    file = "transactions_lacking.csv"
    path = tmp_path / file
    shutil.copyfile(data_path / file, path)
    path_debug = empty_portfolio.path.with_suffix(".importer_debug")

    c = Import(empty_portfolio.path, None, [path], force=False)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
    target = (
        f"{Fore.RED}Unknown importer for {path}\n"
        f"{Fore.YELLOW}Create a custom importer in {empty_portfolio.importers_path}\n"
        f"{Fore.RED}Abandoned import, restored from backup\n"
        f"{Fore.YELLOW}Raw imported file may help at {path_debug}\n"
    )
    assert captured.err == target

    assert path_debug.exists()


def test_duplicate(
    capsys: pytest.CaptureFixture,
    today: datetime.date,
    empty_portfolio: Portfolio,
    account: Account,
    account_investments: Account,
    asset: Asset,
    tmp_path: Path,
    data_path: Path,
) -> None:
    _ = account
    _ = account_investments
    _ = asset
    file = "transactions_required.csv"
    path = tmp_path / file
    shutil.copyfile(data_path / file, path)
    path_debug = empty_portfolio.path.with_suffix(".importer_debug")

    c = Import(empty_portfolio.path, None, [path, path], force=False)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
    target = (
        f"{Fore.RED}Already imported {path} on {today}\n"
        f"{Fore.YELLOW}Delete file or run import with --force flag which "
        "may create duplicate transactions.\n"
        f"{Fore.RED}Abandoned import, restored from backup\n"
    )
    assert captured.err == target

    assert not path_debug.exists()


@pytest.mark.xfail
def test_data_dir_no_account(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    data_path: Path,
) -> None:
    path_debug = empty_portfolio.path.with_suffix(".importer_debug")

    # BUG (WattsUp): #367 Currently it raises NoResultFound due to missing Account
    # It should prompt to create the account instead
    # Same for Asset, probably
    c = Import(empty_portfolio.path, None, [data_path], force=False)
    assert c.run() != 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    target = (
        f"{Fore.RED}Abandoned import, restored from backup\n"
        f"{Fore.YELLOW}Raw imported file may help at {path_debug}\n"
    )
    assert captured.err == target
