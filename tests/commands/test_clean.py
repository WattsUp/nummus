from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus.commands.clean import Clean

if TYPE_CHECKING:
    import pytest

    from nummus.portfolio import Portfolio


def test_clean(capsys: pytest.CaptureFixture, empty_portfolio: Portfolio) -> None:
    c = Clean(empty_portfolio.path, None)
    assert c.run() == 0

    path_backup = empty_portfolio.path.with_suffix(".backup1.tar")
    assert path_backup.exists()

    captured = capsys.readouterr()
    target = (
        f"{Fore.GREEN}Portfolio is unlocked\n"
        f"{Fore.GREEN}Portfolio cleaned\n"
        f"{Fore.CYAN}Portfolio was optimized by 0.0KB/0.0KiB\n"
    )
    assert captured.out == target
    assert not captured.err
