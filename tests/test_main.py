from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from colorama import Fore

from nummus import main, version

if TYPE_CHECKING:
    from nummus.portfolio import Portfolio


def test_entrypoints() -> None:
    # Check can execute entrypoint
    path = Path(sys.executable).with_name("nummus")
    with subprocess.Popen(  # noqa: S603
        [str(path), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    ) as process:
        stdout, stderr = process.communicate()
        stdout = stdout.decode().strip("\r\n").strip("\n")
        stderr = stderr.decode().strip("\r\n").strip("\n")
        assert not stderr
        assert stdout == version.__version__


def test_unlock_non_existant(empty_portfolio: Portfolio) -> None:
    # Try unlocking non-existent Portfolio
    args = [
        "--portfolio",
        str(empty_portfolio.path.with_suffix(".non-existent")),
        "unlock",
    ]
    with pytest.raises(SystemExit):
        main.main(args)


def test_unlock_successful(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:
    args = ["--portfolio", str(empty_portfolio.path), "unlock"]
    assert main.main(args) == 0
    assert capsys.readouterr().out == f"{Fore.GREEN}Portfolio is unlocked\n"
