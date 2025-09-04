from __future__ import annotations

import sys
from typing import override, TYPE_CHECKING

from colorama import Fore

from nummus.commands.create import Create
from nummus.portfolio import Portfolio

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class MockPortfolio(Portfolio):

    def __init__(self) -> None:
        pass

    # Creating takes a long time so mock actual function
    @override
    @classmethod
    def create(cls, path: str | Path, key: str | None = None) -> Portfolio:
        print(f"Creating {path} with {key}", file=sys.stderr)
        return MockPortfolio()


def test_create_existing(
    capsys: pytest.CaptureFixture,
    tmp_path: Path,
) -> None:
    path = tmp_path / "new.db"
    path.touch()

    c = Create(path, None, force=False, no_encrypt=True)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert not captured.out
    target = f"{Fore.RED}Cannot overwrite portfolio at {path}. Try with --force\n"
    assert captured.err == target


def test_create_unencrypted_forced(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "new.db"
    path.touch()
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    c = Create(path, None, force=True, no_encrypt=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio created at {path}\n"
    assert captured.out == target
    target = f"Creating {path} with None\n"
    assert captured.err == target


def test_create_unencrypted(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "new.db"
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    c = Create(path, None, force=False, no_encrypt=True)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio created at {path}\n"
    assert captured.out == target
    target = f"Creating {path} with None\n"
    assert captured.err == target


def test_create_encrypted(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rand_str: str,
) -> None:
    path = tmp_path / "new.db"
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    queue = [rand_str, rand_str]

    def mock_get_pass(_: str) -> str | None:
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_get_pass)
    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    c = Create(path, None, force=False, no_encrypt=False)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio created at {path}\n"
    assert captured.out == target
    target = f"Creating {path} with {rand_str}\n"
    assert captured.err == target


def test_create_encrypted_pass_file(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    rand_str: str,
) -> None:
    path = tmp_path / "new.db"
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    path_password = tmp_path / "password.secret"
    with path_password.open("w", encoding="utf-8") as file:
        file.write(rand_str)

    c = Create(path, path_password, force=False, no_encrypt=False)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio created at {path}\n"
    assert captured.out == target
    target = f"Creating {path} with {rand_str}\n"
    assert captured.err == target


def test_create_encrypted_cancelled(
    capsys: pytest.CaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "new.db"
    monkeypatch.setattr("nummus.portfolio.Portfolio", MockPortfolio)

    queue = [None]

    def mock_get_pass(_: str) -> str | None:
        return queue.pop(0)

    monkeypatch.setattr("builtins.input", mock_get_pass)
    monkeypatch.setattr("getpass.getpass", mock_get_pass)

    c = Create(path, None, force=False, no_encrypt=False)
    assert c.run() != 0

    captured = capsys.readouterr()
    assert not captured.out
    assert not captured.err
