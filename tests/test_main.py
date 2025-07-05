from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

import pytest
from colorama import Fore

from nummus import main, version

if TYPE_CHECKING:
    from tests.conftest import EmptyPortfolio


def test_entrypoints() -> None:
    # Check can execute entrypoint
    with subprocess.Popen(
        ["nummus", "--version"],  # noqa: S607
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        stdout, stderr = process.communicate()
        stdout = stdout.decode().strip("\r\n").strip("\n")
        stderr = stderr.decode().strip("\r\n").strip("\n")
        assert not stderr
        assert stdout == version.__version__


def test_unlock_non_existant(empty_portfolio: EmptyPortfolio) -> None:
    p = empty_portfolio()

    # Try unlocking non-existent Portfolio
    args = ["--portfolio", str(p.path.with_suffix(".non-existent")), "unlock"]
    with pytest.raises(SystemExit):
        main.main(args)


def test_unlock_successful(
    capsys: pytest.CaptureFixture,
    empty_portfolio: EmptyPortfolio,
) -> None:
    p = empty_portfolio()
    args = ["--portfolio", str(p.path), "unlock"]
    assert main.main(args) == 0
    assert capsys.readouterr().out == f"{Fore.GREEN}Portfolio is unlocked\n"
