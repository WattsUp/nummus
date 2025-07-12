from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from colorama import Fore
from typing_extensions import override

from nummus import encryption
from nummus.commands.change_password import ChangePassword
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


class MockPortfolio(Portfolio):

    # Changing password takes a while so mock the actual function
    @override
    def change_key(self, key: str) -> None:
        print(f"Changing key to {key}", file=sys.stderr)  # noqa: T201

    @override
    def change_web_key(self, key: str) -> None:
        print(f"Changing web key to {key}", file=sys.stderr)  # noqa: T201


def test_no_change_unencrypted(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio: Portfolio,
) -> None:
    queue = [None]

    def mock_get_pass(_: str) -> str | None:
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_get_pass)
    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    c = ChangePassword(empty_portfolio.path, None)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.err == f"{Fore.YELLOW}Neither password changing\n"


@pytest.mark.parametrize(
    ("queue", "target"),
    [
        ([None, None], f"{Fore.YELLOW}Neither password changing\n"),
        (["Y", None], ""),
        ([None, "Y", None], ""),
    ],
)
@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_no_change(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
    tmp_path: Path,
    queue: list[str],
    target: str,
) -> None:
    p, key = empty_portfolio_encrypted
    path_password = tmp_path / "password.secret"
    with path_password.open("w", encoding="utf-8") as file:
        file.write(key)

    def mock_get_pass(_: str) -> str | None:
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_get_pass)
    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    c = ChangePassword(p.path, path_password)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.err == target


@pytest.mark.parametrize(
    ("queue", "target"),
    [
        (["Y", "12345678", "12345678", "N"], "Changing key to 12345678\n"),
        (["N", "Y", "01010101", "01010101"], "Changing web key to 01010101\n"),
        (
            ["Y", "12345678", "12345678", "Y", "01010101", "01010101"],
            "Changing key to 12345678\nChanging web key to 01010101\n",
        ),
    ],
)
@pytest.mark.skipif(not encryption.AVAILABLE, reason="Encryption is not installed")
@pytest.mark.encryption
def test_change(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio_encrypted: tuple[Portfolio, str],
    tmp_path: Path,
    queue: list[str],
    target: str,
) -> None:
    p, key = empty_portfolio_encrypted
    path_password = tmp_path / "password.secret"
    with path_password.open("w", encoding="utf-8") as file:
        file.write(key)

    def mock_get_pass(_: str) -> str | None:
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_get_pass)
    monkeypatch.setattr("getpass.getpass", mock_get_pass)
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    c = ChangePassword(p.path, path_password)
    assert c.run() == 0

    captured = capsys.readouterr()
    assert (
        captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}Changed password(s)\n"
        f"{Fore.CYAN}Run 'nummus clean' to remove backups with old password\n"
    )
    assert captured.err == target
