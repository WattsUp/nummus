from __future__ import annotations

import sys
from typing import override, TYPE_CHECKING

import pytest
from colorama import Fore

from nummus.commands.change_password import ChangePassword
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path


class MockPortfolio(Portfolio):

    # Changing password takes a while so mock the actual function
    @override
    def change_key(self, key: str) -> None:
        print(f"Changing key to {key}", file=sys.stderr)

    @override
    def change_web_key(self, key: str) -> None:
        print(f"Changing web key to {key}", file=sys.stderr)


def test_no_change_unencrypted(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
    tmp_path: Path,
) -> None:
    path_password_new = tmp_path / "password.secret"
    with path_password_new.open("w", encoding="utf-8") as file:
        file.write("db:\n")
        file.write("web:\n")

    c = ChangePassword(empty_portfolio.path, None, path_password_new)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert captured.out == f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.err == f"{Fore.YELLOW}Neither password changing\n"


@pytest.mark.parametrize(
    ("new_db_key", "new_web_key", "target"),
    [
        ("12345678", "", "Changing key to 12345678\n"),
        ("", "01010101", "Changing web key to 01010101\n"),
    ],
)
def test_change(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio: Portfolio,
    tmp_path: Path,
    new_db_key: str,
    new_web_key: str,
    target: str,
) -> None:
    path_password_new = tmp_path / "password.secret"
    with path_password_new.open("w", encoding="utf-8") as file:
        file.write(f"db:{new_db_key}\n")
        file.write(f"web:{new_web_key}\n")
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    c = ChangePassword(empty_portfolio.path, None, path_password_new)
    assert c.run() == 0

    captured = capsys.readouterr()
    target_out = (
        f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}Changed password(s)\n"
        f"{Fore.CYAN}Run 'nummus clean' to remove backups with old password\n"
    )
    assert captured.out == target_out
    assert captured.err == target


@pytest.mark.parametrize(
    ("queue", "target_db", "target_web"),
    [
        (["N"], None, None),
        (["Y", None], None, None),
        (["Y", "12345678", "12345678", "N"], "12345678", None),
        (["Y", "12345678", "12345678", "Y", None], None, None),
        (
            ["Y", "12345678", "12345678", "Y", "01010101", "01010101"],
            "12345678",
            "01010101",
        ),
    ],
)
def test_get_keys_input(
    monkeypatch: pytest.MonkeyPatch,
    empty_portfolio: Portfolio,
    queue: list[str],
    target_db: str | None,
    target_web: str | None,
) -> None:
    def mock_get_pass(_: str) -> str | None:
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_get_pass)
    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    c = ChangePassword(empty_portfolio.path, None, None)
    new_db_key, new_web_key = c._get_keys()

    assert new_db_key == target_db
    assert new_web_key == target_web


def test_get_keys_file(
    empty_portfolio: Portfolio,
    tmp_path: Path,
) -> None:
    path_password_new = tmp_path / "password.secret"
    with path_password_new.open("w", encoding="utf-8") as file:
        file.write("db:12345678\n")
        file.write("web:01010101\n")

    c = ChangePassword(empty_portfolio.path, None, path_password_new)
    new_db_key, new_web_key = c._get_keys()

    assert new_db_key == "12345678"
    assert new_web_key == "01010101"
