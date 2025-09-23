from __future__ import annotations

import argparse
import sys
from typing import override, TYPE_CHECKING

import pytest
from colorama import Fore

from nummus import encryption, migrations
from nummus.commands.backup import Backup, Restore
from nummus.commands.base import BaseCommand
from nummus.commands.change_password import ChangePassword
from nummus.commands.clean import Clean
from nummus.commands.create import Create
from nummus.commands.export import Export
from nummus.commands.health import Health
from nummus.commands.import_files import Import
from nummus.commands.migrate import Migrate
from nummus.commands.summarize import Summarize
from nummus.commands.unlock import Unlock
from nummus.commands.update_assets import UpdateAssets

if TYPE_CHECKING:
    from pathlib import Path

    from nummus.portfolio import Portfolio


class MockCommand(BaseCommand):

    @classmethod
    def setup_args(cls, parser: argparse.ArgumentParser) -> None:
        _ = parser

    @override
    def run(self) -> int:
        return 0


def test_no_unlock(tmp_path: Path) -> None:
    MockCommand(tmp_path / "fake.db", None, do_unlock=False)


def test_no_file(capsys: pytest.CaptureFixture, tmp_path: Path) -> None:
    path = tmp_path / "fake.db"
    with pytest.raises(SystemExit):
        MockCommand(path, None)

    captured = capsys.readouterr()
    assert not captured.out
    target = f"{Fore.RED}Portfolio does not exist at {path}. Run nummus create\n"
    assert captured.err == target


def test_unlock(capsys: pytest.CaptureFixture, empty_portfolio: Portfolio) -> None:
    MockCommand(empty_portfolio.path, None)

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    assert not captured.err


def test_migration_required(capsys: pytest.CaptureFixture, data_path: Path) -> None:
    with pytest.raises(SystemExit):
        MockCommand(data_path / "old_versions" / "v0.1.16.db", None)

    captured = capsys.readouterr()
    assert not captured.out
    v = migrations.MIGRATORS[-1].min_version()
    target = (
        f"{Fore.RED}Portfolio requires migration to v{v}\n"
        f"{Fore.YELLOW}Run 'nummus migrate' to resolve\n"
    )
    assert captured.err == target


@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_unlock_encrypted_path(
    capsys: pytest.CaptureFixture,
    empty_portfolio_encrypted: tuple[Portfolio, str],
    tmp_path: Path,
) -> None:
    p, key = empty_portfolio_encrypted
    path_password = tmp_path / "password.secret"
    with path_password.open("w", encoding="utf-8") as file:
        file.write(key)

    MockCommand(p.path, path_password)

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    assert not captured.err


@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_unlock_encrypted_path_bad_key(
    capsys: pytest.CaptureFixture,
    empty_portfolio_encrypted: tuple[Portfolio, str],
    tmp_path: Path,
) -> None:
    p, _ = empty_portfolio_encrypted
    path_password = tmp_path / "password.secret"
    with path_password.open("w", encoding="utf-8") as file:
        file.write("not key")

    with pytest.raises(SystemExit):
        MockCommand(p.path, path_password)

    captured = capsys.readouterr()
    assert not captured.out
    target = f"{Fore.RED}Could not decrypt with password file\n"
    assert captured.err == target


@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_unlock_encrypted(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> None:
    p, key = empty_portfolio_encrypted
    queue = ["not key", key]

    def mock_get_pass(to_print: str) -> str | None:
        print(to_print, file=sys.stderr)
        return queue.pop(0)

    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    MockCommand(p.path, None)

    captured = capsys.readouterr()
    assert captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
    target = (
        "\u26bf  Please enter password: \n"
        f"{Fore.RED}Incorrect password\n"
        "\u26bf  Please enter password: \n"
    )
    assert captured.err == target


@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_unlock_encrypted_cancel(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> None:
    p, _ = empty_portfolio_encrypted

    def mock_get_pass(to_print: str) -> str | None:
        print(to_print, file=sys.stderr)
        return None

    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    with pytest.raises(SystemExit):
        MockCommand(p.path, None)

    captured = capsys.readouterr()
    assert not captured.out
    target = "\u26bf  Please enter password: \n"
    assert captured.err == target


@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_unlock_encrypted_failed(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
) -> None:
    p, _ = empty_portfolio_encrypted

    def mock_get_pass(to_print: str) -> str | None:
        print(to_print, file=sys.stderr)
        return "not key"

    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    with pytest.raises(SystemExit):
        MockCommand(p.path, None)

    captured = capsys.readouterr()
    assert not captured.out
    target = (
        "\u26bf  Please enter password: \n"
        f"{Fore.RED}Incorrect password\n"
        "\u26bf  Please enter password: \n"
        f"{Fore.RED}Incorrect password\n"
        "\u26bf  Please enter password: \n"
        f"{Fore.RED}Incorrect password\n"
        f"{Fore.RED}Too many incorrect attempts\n"
    )
    assert captured.err == target


@pytest.mark.parametrize(
    ("cmd_class", "extra_args"),
    [
        (Create, []),
        (Unlock, []),
        (Migrate, []),
        (Backup, []),
        (Restore, []),
        (Clean, []),
        (Import, ["/dev/null"]),
        (Export, ["/dev/null"]),
        (UpdateAssets, []),
        (Health, []),
        (Summarize, []),
        (ChangePassword, []),
    ],
)
def test_args(
    empty_portfolio: Portfolio,
    cmd_class: type[BaseCommand],
    extra_args: list[str],
) -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="cmd",
        metavar="<command>",
        required=True,
    )

    sub = subparsers.add_parser(
        cmd_class.NAME,
        help=cmd_class.HELP,
        description=cmd_class.DESCRIPTION,
    )
    cmd_class.setup_args(sub)

    command_line = [cmd_class.NAME, *extra_args]
    args = parser.parse_args(args=command_line)
    args_d = vars(args)
    args_d["path_db"] = empty_portfolio.path
    args_d["path_password"] = None
    cmd: str = args_d.pop("cmd")
    assert cmd == cmd_class.NAME

    # Make sure all args from parse_args are given to constructor
    cmd_class(**args_d)
