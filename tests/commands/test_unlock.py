from __future__ import annotations

from typing import TYPE_CHECKING

from colorama import Fore

from nummus.commands.unlock import Unlock

if TYPE_CHECKING:

    import pytest

    from nummus.portfolio import Portfolio


def test_empty(
    capsys: pytest.CaptureFixture,
    empty_portfolio: Portfolio,
) -> None:

    c = Unlock(empty_portfolio.path, None)
    assert c.run() == 0

    captured = capsys.readouterr()
    target = f"{Fore.GREEN}Portfolio is unlocked\n"
    assert captured.out == target
    assert not captured.err
