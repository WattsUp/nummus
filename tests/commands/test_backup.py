from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus.commands.backup import Backup, Restore

if TYPE_CHECKING:
    import datetime

    import pytest

    from nummus.portfolio import Portfolio


def test_backup(capsys: pytest.CaptureFixture, empty_portfolio: Portfolio) -> None:
    c = Backup(empty_portfolio.path, None)
    assert c.run() == 0

    path_backup = empty_portfolio.path.with_suffix(".backup1.tar")
    assert path_backup.exists()

    captured = capsys.readouterr()
    target = (
        f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}Portfolio backed up to {path_backup}\n"
    )
    assert captured.out == target
    assert not captured.err


def test_restore(capsys: pytest.CaptureFixture, empty_portfolio: Portfolio) -> None:
    empty_portfolio.backup()
    c = Restore(empty_portfolio.path, None, tar_ver=None, list_ver=False)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = (
        f"{Fore.CYAN}Extracted backup tar\n"
        f"{Fore.GREEN}Portfolio restored for {empty_portfolio.path}\n"
    )
    assert captured.out == target
    assert not captured.err


def test_restore_missing(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:
    c = Restore(empty_portfolio.path, None, tar_ver=None, list_ver=False)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert not captured.out
    target = f"{Fore.RED}No backup exists for {empty_portfolio.path}\n"
    assert captured.err == target


def test_restore_list_empty(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:
    c = Restore(empty_portfolio.path, None, tar_ver=None, list_ver=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    assert not captured.out
    target = f"{Fore.RED}No backups found, run 'nummus backup'\n"
    assert captured.err == target


def test_restore_list(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    utc_frozen: datetime.datetime,
) -> None:
    empty_portfolio.backup()
    c = Restore(empty_portfolio.path, None, tar_ver=None, list_ver=True)
    assert c.run() == 0

    ts_local = utc_frozen.astimezone().isoformat(timespec="seconds")

    captured = capsys.readouterr()
    target = f"{Fore.CYAN}Backup # 1 created at {ts_local} (0.0 seconds ago)\n"
    assert captured.out == target
    assert not captured.err
